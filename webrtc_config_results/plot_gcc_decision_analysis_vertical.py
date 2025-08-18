#!/usr/bin/env python3
"""
WebRTC GCC (Google Congestion Control) Decision Process Analyzer

This script parses logs containing GCC-DECISION-SNAPSHOT entries and generates
comprehensive visualization charts showing the four-layer priority decision process:
Delay-based, RTT backoff, Probe-based, and Loss-based bandwidth estimation.
"""

import re
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

class GccDecisionAnalyzer:
    """
    A specialized class for parsing and visualizing GCC decision process logs.
    """
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        
        # Regular expressions to match key log entries
        self.patterns = {
            # GCC Decision Snapshot
            'decision': re.compile(r'\[GCC-DECISION-SNAPSHOT\] at (\d+)ms \| DelayState: (\w+), DelayTargetBps: (\d+) \| RttBackoff: (\w+) \| ProbeResultBps: (\d+) \| BweTargetBps: (\d+) \| AckedBitrateBps: (\d+) \| FinalTargetBps: (\d+) \| DecisionReason: (\w+) \| Updated: (\w+)'),
            # Trendline analysis (Delay BWE internal)
            'trendline': re.compile(r'\[Trendline\] Time: (\d+) ms.*?Modified trend: ([^,]+), Threshold: ([^,]+), State: (\w+)'),
            # RTT BWE internal parameters
            'rtt_bwe': re.compile(r'\[RttBWE-Update\] Time: (\d+) ms, PropagationRtt: (\d+) ms, CorrectedRtt: (\d+) ms, RttLimit: (\d+) ms, AboveLimit: (\w+)'),
            # Loss BWE internal parameters  
            'loss_bwe': re.compile(r'\[LossBWE-Estimate\] Time: (\d+) ms, State: (\d+), Bandwidth: (\d+) bps, Observations: (\d+)'),
            # Loss BWE candidates
            'loss_candidates': re.compile(r'\[LossBWE-Candidates\] Time: (\d+) ms, Candidate Bandwidths \(kbps\): (.+)'),
            # Delay BWE decisions
            'delay_bwe': re.compile(r'\[DelayBWE-Decision\] Time: (\d+) ms.*?New bitrate: (\d+) bps.*?Probe: (\w+)'),
            # Probe results: Updated patterns for timestamped logs
            'probe_result': re.compile(r'\[ProbeBWE-Result\] Time: (\d+) ms, Cluster ID: (\d+), Final estimate: (\d+) bps'),
            'probe_success': re.compile(r'\[ProbeBWE-Success\] Time: (\d+) ms, Cluster ID: (\d+), Send rate: (\d+) bps'),
            # Fallback patterns for old format (without timestamps)
            'probe_result_old': re.compile(r'\[ProbeBWE-Result\] Cluster ID: (\d+), Final estimate: (\d+) bps'),
            'probe_success_old': re.compile(r'\[ProbeBWE-Success\] Cluster ID: (\d+), Send rate: (\d+) bps'),
            
            # New constraint tracking patterns
            'constraint_apply': re.compile(r'\[BWE-ConstraintApply\] Time: (\d+) ms, Original: (\d+) bps, UpperLimit: (\d+) bps, AfterUpper: (\d+) bps, MinConfig: (\d+) bps, Final: (\d+) bps, DelayLimit: (\d+) bps, ReceiverLimit: (\d+) bps, MaxConfig: (\d+) bps'),
            'delay_limit': re.compile(r'\[BWE-DelayLimit\] Time: (\d+) ms, OldLimit: (\d+) bps, NewLimit: (\d+) bps, CurrentTarget: (\d+) bps'),
            'receiver_limit': re.compile(r'\[BWE-ReceiverLimit\] Time: (\d+) ms, OldLimit: (\d+) bps, NewLimit: (\d+) bps, CurrentTarget: (\d+) bps'),
            'config_limit': re.compile(r'\[BWE-ConfigLimit\] MinBitrate: (\d+) -> (\d+) bps, MaxBitrate: (\d+) -> (\d+) bps, CurrentTarget: (\d+) bps'),
            'pushback': re.compile(r'\[BWE-CongestionWindowPushback\] Time: (\d+) ms, OriginalRate: (\d+) bps, PushbackRate: (\d+) bps, MinBitrate: (\d+) bps, Reduction: (\d+) bps, ReductionRatio: ([^%]+)%')
        }

    def parse_log_file(self):
        """
        Parse the log file and extract internal BWE engine parameters.
        """
        print(f"[*] Parsing log file: {self.log_file_path}")
        
        # Separate data collections for each BWE engine
        trendline_data = []
        rtt_data = []
        loss_data = []
        probe_data = []
        decision_data = []
        
        # New constraint tracking data collections
        constraint_apply_data = []
        delay_limit_data = []
        receiver_limit_data = []
        config_limit_data = []
        pushback_data = []
        
        # Track the most recent timestamp for lines without explicit timestamps
        last_timestamp = None

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Extract timestamp from any line that has one
                timestamp_match = re.search(r'Time: (\d+) ms|at (\d+) ms', line)
                if timestamp_match:
                    last_timestamp = int(timestamp_match.group(1) or timestamp_match.group(2))
                    
                # Match Trendline data (Delay BWE internal)
                trendline_match = self.patterns['trendline'].search(line)
                if trendline_match:
                    timestamp = int(trendline_match.group(1))
                    modified_trend = trendline_match.group(2)
                    threshold = trendline_match.group(3)
                    state = trendline_match.group(4)
                    
                    # Handle 'nan' values
                    try:
                        modified_trend_val = float(modified_trend) if modified_trend != 'nan' else 0.0
                    except:
                        modified_trend_val = 0.0
                    
                    try:
                        threshold_val = float(threshold)
                    except:
                        threshold_val = 0.0
                        
                    trendline_data.append({
                        'timestamp': timestamp,
                        'modified_trend': modified_trend_val,
                        'threshold': threshold_val,
                        'state': state
                    })
                    continue

                # Match RTT BWE data
                rtt_match = self.patterns['rtt_bwe'].search(line)
                if rtt_match:
                    timestamp = int(rtt_match.group(1))
                    corrected_rtt = int(rtt_match.group(3))
                    rtt_limit = int(rtt_match.group(4))
                    above_limit = rtt_match.group(5) == 'true'
                    
                    rtt_data.append({
                        'timestamp': timestamp,
                        'corrected_rtt': corrected_rtt,
                        'rtt_limit': rtt_limit,
                        'above_limit': above_limit
                    })
                    continue

                # Match Loss BWE data
                loss_match = self.patterns['loss_bwe'].search(line)
                if loss_match:
                    timestamp = int(loss_match.group(1))
                    state = int(loss_match.group(2))
                    bandwidth = int(loss_match.group(3))
                    observations = int(loss_match.group(4))
                    
                    loss_data.append({
                        'timestamp': timestamp,
                        'state': state,
                        'bandwidth': bandwidth,
                        'observations': observations
                    })
                    continue

                # Match Loss BWE candidates data
                candidates_match = self.patterns['loss_candidates'].search(line)
                if candidates_match:
                    timestamp = int(candidates_match.group(1))
                    candidates_str = candidates_match.group(2)
                    # Parse candidate bandwidths (they end with comma and space)
                    candidates = [float(x.strip().rstrip(',')) for x in candidates_str.split(',') if x.strip().rstrip(',')]
                    
                    loss_data.append({
                        'timestamp': timestamp,
                        'state': -1,  # Special marker for candidates
                        'bandwidth': int(max(candidates) * 1000) if candidates else 0,  # Convert back to bps
                        'observations': len(candidates),
                        'candidates': candidates
                    })
                    continue

                # Match Probe BWE results with explicit timestamps (new format)
                probe_result_match = self.patterns['probe_result'].search(line)
                if probe_result_match:
                    timestamp = int(probe_result_match.group(1))
                    cluster_id = int(probe_result_match.group(2))
                    estimate = int(probe_result_match.group(3))
                    
                    probe_data.append({
                        'timestamp': timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'result'
                    })
                    continue

                # Match Probe BWE success with explicit timestamps (new format)
                probe_success_match = self.patterns['probe_success'].search(line)
                if probe_success_match:
                    timestamp = int(probe_success_match.group(1))
                    cluster_id = int(probe_success_match.group(2))
                    estimate = int(probe_success_match.group(3))  # Use send rate as estimate
                    
                    probe_data.append({
                        'timestamp': timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'success'
                    })
                    continue

                # Fallback: Match old format without explicit timestamps
                probe_result_old_match = self.patterns['probe_result_old'].search(line)
                if probe_result_old_match and last_timestamp:
                    cluster_id = int(probe_result_old_match.group(1))
                    estimate = int(probe_result_old_match.group(2))
                    
                    probe_data.append({
                        'timestamp': last_timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'result_old'
                    })
                    continue

                probe_success_old_match = self.patterns['probe_success_old'].search(line)
                if probe_success_old_match and last_timestamp:
                    cluster_id = int(probe_success_old_match.group(1))
                    estimate = int(probe_success_old_match.group(2))
                    
                    probe_data.append({
                        'timestamp': last_timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'success_old'
                    })
                    continue

                # Match GCC decision snapshots for final decision
                decision_match = self.patterns['decision'].search(line)
                if decision_match:
                    timestamp = int(decision_match.group(1))
                    decision_reason = decision_match.group(9)
                    
                    decision_data.append({
                        'timestamp': timestamp,
                        'decision_reason': decision_reason
                    })
                    continue

                # Match constraint application logs
                constraint_match = self.patterns['constraint_apply'].search(line)
                if constraint_match:
                    timestamp = int(constraint_match.group(1))
                    original = int(constraint_match.group(2))
                    upper_limit = int(constraint_match.group(3))
                    after_upper = int(constraint_match.group(4))
                    min_config = int(constraint_match.group(5))
                    final = int(constraint_match.group(6))
                    delay_limit = int(constraint_match.group(7))
                    receiver_limit = int(constraint_match.group(8))
                    max_config = int(constraint_match.group(9))
                    
                    constraint_apply_data.append({
                        'timestamp': timestamp,
                        'original': original,
                        'upper_limit': upper_limit,
                        'after_upper': after_upper,
                        'min_config': min_config,
                        'final': final,
                        'delay_limit': delay_limit,
                        'receiver_limit': receiver_limit,
                        'max_config': max_config
                    })
                    continue

                # Match delay limit updates
                delay_limit_match = self.patterns['delay_limit'].search(line)
                if delay_limit_match:
                    timestamp = int(delay_limit_match.group(1))
                    old_limit = int(delay_limit_match.group(2))
                    new_limit = int(delay_limit_match.group(3))
                    current_target = int(delay_limit_match.group(4))
                    
                    delay_limit_data.append({
                        'timestamp': timestamp,
                        'old_limit': old_limit,
                        'new_limit': new_limit,
                        'current_target': current_target
                    })
                    continue

                # Match receiver limit updates
                receiver_limit_match = self.patterns['receiver_limit'].search(line)
                if receiver_limit_match:
                    timestamp = int(receiver_limit_match.group(1))
                    old_limit = int(receiver_limit_match.group(2))
                    new_limit = int(receiver_limit_match.group(3))
                    current_target = int(receiver_limit_match.group(4))
                    
                    receiver_limit_data.append({
                        'timestamp': timestamp,
                        'old_limit': old_limit,
                        'new_limit': new_limit,
                        'current_target': current_target
                    })
                    continue

                # Match pushback logs
                pushback_match = self.patterns['pushback'].search(line)
                if pushback_match:
                    timestamp = int(pushback_match.group(1))
                    original_rate = int(pushback_match.group(2))
                    pushback_rate = int(pushback_match.group(3))
                    min_bitrate = int(pushback_match.group(4))
                    reduction = int(pushback_match.group(5))
                    reduction_ratio = float(pushback_match.group(6))
                    
                    pushback_data.append({
                        'timestamp': timestamp,
                        'original_rate': original_rate,
                        'pushback_rate': pushback_rate,
                        'min_bitrate': min_bitrate,
                        'reduction': reduction,
                        'reduction_ratio': reduction_ratio
                    })
                    continue

        # Convert to DataFrames
        trendline_df = pd.DataFrame(trendline_data)
        rtt_df = pd.DataFrame(rtt_data)
        loss_df = pd.DataFrame(loss_data)
        probe_df = pd.DataFrame(probe_data)
        decision_df = pd.DataFrame(decision_data)
        
        # Convert new constraint data to DataFrames
        constraint_apply_df = pd.DataFrame(constraint_apply_data)
        delay_limit_df = pd.DataFrame(delay_limit_data)
        receiver_limit_df = pd.DataFrame(receiver_limit_data)
        config_limit_df = pd.DataFrame(config_limit_data)
        pushback_df = pd.DataFrame(pushback_data)

        print(f"[*] Parsing completed:")
        print(f"  Trendline data points: {len(trendline_df)}")
        print(f"  RTT data points: {len(rtt_df)}")
        print(f"  Loss data points: {len(loss_df)}")
        print(f"  Probe data points: {len(probe_df)}")
        print(f"  Decision data points: {len(decision_df)}")
        print(f"  Constraint apply data points: {len(constraint_apply_df)}")
        print(f"  Delay limit data points: {len(delay_limit_df)}")
        print(f"  Receiver limit data points: {len(receiver_limit_df)}")
        print(f"  Config limit data points: {len(config_limit_df)}")
        print(f"  Pushback data points: {len(pushback_df)}")
        
        return {
            'trendline': trendline_df,
            'rtt': rtt_df,
            'loss': loss_df,
            'probe': probe_df,
            'decision': decision_df,
            'constraint_apply': constraint_apply_df,
            'delay_limit': delay_limit_df,
            'receiver_limit': receiver_limit_df,
            'config_limit': config_limit_df,
            'pushback': pushback_df
        }

    def plot_gcc_decision_metrics(self, data_dict):
        """
        Plot GCC internal parameters comparison using 5 vertical subplots.
        """
        trendline_df = data_dict['trendline']
        rtt_df = data_dict['rtt'] 
        loss_df = data_dict['loss']
        probe_df = data_dict['probe']
        decision_df = data_dict['decision']
        
        if trendline_df.empty and rtt_df.empty and loss_df.empty:
            print("[!] Insufficient data to generate charts.")
            return None
        
        # Set matplotlib style
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            plt.style.use('default')
            
        # Create 5 vertical subplots
        fig, axes = plt.subplots(5, 1, figsize=(16, 20), sharex=True)
        fig.suptitle(f'WebRTC GCC Internal Parameters Analysis\n({self.log_file_path})', 
                     fontsize=16, fontweight='bold')

        # Determine common time range
        all_timestamps = []
        if not trendline_df.empty:
            all_timestamps.extend(trendline_df['timestamp'].tolist())
        if not rtt_df.empty:
            all_timestamps.extend(rtt_df['timestamp'].tolist())
        if not decision_df.empty:
            all_timestamps.extend(decision_df['timestamp'].tolist())
            
        if all_timestamps:
            start_time_ms = min(all_timestamps)
            end_time_ms = max(all_timestamps)
            time_limit = (end_time_ms - start_time_ms) / 1000.0 + 1.0
            print(f"[*] Chart will display time range: 0 - {time_limit:.1f} seconds")
            print(f"[*] Timestamps: {start_time_ms} - {end_time_ms}")
        else:
            start_time_ms = 0
            time_limit = 10.0

        # 1. Delay BWE Internal: Modified Trend vs Threshold
        if not trendline_df.empty:
            trendline_df['time_s'] = (trendline_df['timestamp'] - start_time_ms) / 1000.0
            
            axes[0].plot(trendline_df['time_s'], trendline_df['modified_trend'], 'o-', 
                        color='blue', label='Modified Trend', markersize=3, linewidth=2)
            axes[0].plot(trendline_df['time_s'], trendline_df['threshold'], '-', 
                        color='red', label='Threshold', linewidth=2, alpha=0.8)
            
            # Fill area between trend and threshold when trend > threshold (overusing)
            axes[0].fill_between(trendline_df['time_s'], trendline_df['modified_trend'], 
                               trendline_df['threshold'], 
                               where=(trendline_df['modified_trend'] > trendline_df['threshold']),
                               color='red', alpha=0.3, label='Overusing Region')
            
            axes[0].set_ylabel('Trend/Threshold', fontsize=11)
            axes[0].set_title('1. Delay BWE: Modified Trend vs Threshold (Internal Decision)', 
                             fontsize=12, fontweight='bold')
            axes[0].grid(True, alpha=0.3)
            
            # Add statistics
            overusing_count = (trendline_df['modified_trend'] > trendline_df['threshold']).sum()
            total_count = len(trendline_df)
            axes[0].text(0.02, 0.95, f'Overusing: {overusing_count}/{total_count} points ({overusing_count/total_count*100:.1f}%)', 
                        transform=axes[0].transAxes, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), fontsize=9)
            axes[0].legend(fontsize=10)

        # 2. RTT BWE Internal: CorrectedRtt vs RttLimit
        if not rtt_df.empty:
            rtt_df['time_s'] = (rtt_df['timestamp'] - start_time_ms) / 1000.0
            
            axes[1].plot(rtt_df['time_s'], rtt_df['corrected_rtt'], 'o-', 
                        color='green', label='CorrectedRtt (ms)', markersize=3, linewidth=2)
            axes[1].axhline(rtt_df['rtt_limit'].iloc[0], color='red', linestyle='--', 
                           linewidth=2, label=f'RTT Limit ({rtt_df["rtt_limit"].iloc[0]} ms)')
            
            # Fill area when RTT > limit (backoff region)
            axes[1].fill_between(rtt_df['time_s'], rtt_df['corrected_rtt'], 
                               rtt_df['rtt_limit'],
                               where=(rtt_df['corrected_rtt'] > rtt_df['rtt_limit']),
                               color='red', alpha=0.3, label='Backoff Region')
            
            axes[1].set_ylabel('RTT (ms)', fontsize=11)
            axes[1].set_title('2. RTT BWE: CorrectedRtt vs Limit (Internal Decision)', 
                             fontsize=12, fontweight='bold')
            
            # Set reasonable Y-axis limit based on data range
            max_rtt = max(rtt_df['corrected_rtt'].max(), rtt_df['rtt_limit'].iloc[0])
            y_limit = min(max_rtt * 1.2, 300)  # Cap at 300ms or 120% of max RTT
            axes[1].set_ylim(0, y_limit)
            
            axes[1].grid(True, alpha=0.3)
            
            # Add statistics
            backoff_count = (rtt_df['corrected_rtt'] > rtt_df['rtt_limit']).sum()
            total_count = len(rtt_df)
            avg_rtt = rtt_df['corrected_rtt'].mean()
            axes[1].text(0.02, 0.95, f'Backoff: {backoff_count}/{total_count} points, Avg RTT: {avg_rtt:.1f}ms', 
                        transform=axes[1].transAxes, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5), fontsize=9)
            axes[1].legend(fontsize=10)

        # 3. Loss BWE Internal: State, Bandwidth, Observations
        if not loss_df.empty:
            # Filter out candidates data (state = -1) for main plot
            estimates_df = loss_df[loss_df['state'] >= 0]
            candidates_df = loss_df[loss_df['state'] == -1]
            
            if not estimates_df.empty:
                # Convert timestamps to relative time
                estimates_df = estimates_df.copy()
                estimates_df['time_s'] = (estimates_df['timestamp'] - start_time_ms) / 1000.0
                
                # Primary axis for bandwidth (line plot)
                axes[2].plot(estimates_df['time_s'], estimates_df['bandwidth']/1000, 
                            'o-', color='purple', label='Bandwidth (kbps)', 
                            markersize=4, linewidth=2, alpha=0.8)
                
                # Secondary axis for state
                ax2_twin = axes[2].twinx()
                ax2_twin.plot(estimates_df['time_s'], estimates_df['state'], 'o-', color='red', 
                             label='State', markersize=4, linewidth=2)
                ax2_twin.set_ylabel('State', fontsize=11, color='red')
                ax2_twin.tick_params(axis='y', labelcolor='red')
                
                # Set integer Y-axis for state (0=Increasing, 1=IncreasingPadding, 2=Decreasing, 3=DelayBased)
                ax2_twin.set_ylim(-0.5, 3.5)
                ax2_twin.set_yticks([0, 1, 2, 3])
                ax2_twin.set_yticklabels(['Increasing', 'IncPadding', 'Decreasing', 'DelayBased'], fontsize=9)
                
                # Add observations as text annotations
                for i, (time, obs) in enumerate(zip(estimates_df['time_s'], estimates_df['observations'])):
                    if i % max(1, len(estimates_df)//10) == 0:  # Show every 10th annotation
                        ax2_twin.text(time, estimates_df['state'].iloc[i] + 0.1, f'{obs}', 
                                     fontsize=8, ha='center', alpha=0.7)
                
                axes[2].set_ylabel('Bandwidth (kbps)', fontsize=11)
                axes[2].set_title('3. Loss BWE: State, Bandwidth & Observations (Time-aligned)', 
                                 fontsize=12, fontweight='bold')
                axes[2].set_ylim(bottom=0)
                axes[2].grid(True, alpha=0.3)
                
                # Add statistics
                avg_bandwidth = estimates_df['bandwidth'].mean() / 1000
                avg_observations = estimates_df['observations'].mean()
                most_common_state = int(estimates_df['state'].mode().iloc[0]) if not estimates_df['state'].empty else 0
                
                # State names mapping
                state_names = {0: 'Increasing', 1: 'IncPadding', 2: 'Decreasing', 3: 'DelayBased'}
                state_name = state_names.get(most_common_state, f'Unknown({most_common_state})')
                
                axes[2].text(0.02, 0.95, f'Avg BW: {avg_bandwidth:.0f}kbps, Obs: {avg_observations:.1f}, State: {state_name}', 
                            transform=axes[2].transAxes, 
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="plum", alpha=0.5), fontsize=9)
                axes[2].legend(fontsize=10)

        # 4. Probe BWE Results
        if not probe_df.empty:
            # Check if we have timestamps for probe data
            has_timestamps = not probe_df['timestamp'].isna().all()
            
            if has_timestamps:
                # Filter out entries without timestamps
                probe_with_time = probe_df.dropna(subset=['timestamp'])
                if not probe_with_time.empty:
                    probe_with_time = probe_with_time.copy()
                    probe_with_time['time_s'] = (probe_with_time['timestamp'] - start_time_ms) / 1000.0
                    
                    # Create scatter plot with time alignment
                    axes[3].scatter(probe_with_time['time_s'], probe_with_time['estimate']/1000, 
                                   c=probe_with_time['cluster_id'], cmap='viridis', 
                                   s=60, alpha=0.8, label='Probe Estimates', edgecolors='black')
                    
                    # Add trend line if there are enough points
                    if len(probe_with_time) > 1:
                        axes[3].plot(probe_with_time['time_s'], probe_with_time['estimate']/1000, 
                                    '--', color='gray', alpha=0.5, linewidth=1)
                    
                    axes[3].set_ylabel('Bandwidth (kbps)', fontsize=11)
                    axes[3].set_title('4. Probe BWE: Bandwidth Estimates by Cluster (Time-aligned)', 
                                     fontsize=12, fontweight='bold')
                    axes[3].set_ylim(bottom=0)
                    axes[3].grid(True, alpha=0.3)
                    
                    # Add statistics
                    avg_estimate = probe_with_time['estimate'].mean() / 1000
                    cluster_count = probe_with_time['cluster_id'].nunique()
                    axes[3].text(0.02, 0.95, f'Avg Estimate: {avg_estimate:.0f}kbps, Clusters: {cluster_count}, Points: {len(probe_with_time)}', 
                                transform=axes[3].transAxes, 
                                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcyan", alpha=0.5), fontsize=9)
                    axes[3].legend(fontsize=10)
                else:
                    # Show message if no timestamps available
                    axes[3].text(0.5, 0.5, 'No Probe Data with Timestamps', 
                                transform=axes[3].transAxes, ha='center', va='center',
                                fontsize=14, alpha=0.5)
                    axes[3].set_title('4. Probe BWE: Bandwidth Estimates by Cluster', 
                                     fontsize=12, fontweight='bold')
                    axes[3].grid(True, alpha=0.3)
            else:
                # Fallback to index-based plotting if no timestamps
                axes[3].scatter(range(len(probe_df)), probe_df['estimate']/1000, 
                               c=probe_df['cluster_id'], cmap='viridis', 
                               s=50, alpha=0.7, label='Probe Estimates')
                
                axes[3].set_ylabel('Bandwidth (kbps)', fontsize=11)
                axes[3].set_title('4. Probe BWE: Bandwidth Estimates by Cluster (Index-based)', 
                                 fontsize=12, fontweight='bold')
                axes[3].set_xlabel('Probe Index')
                axes[3].grid(True, alpha=0.3)
                
                # Add statistics
                avg_estimate = probe_df['estimate'].mean() / 1000
                cluster_count = probe_df['cluster_id'].nunique()
                axes[3].text(0.02, 0.95, f'Avg Estimate: {avg_estimate:.0f}kbps, Clusters: {cluster_count}', 
                            transform=axes[3].transAxes, 
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcyan", alpha=0.5), fontsize=9)
                axes[3].legend(fontsize=10)
        else:
            # Show empty plot with message
            axes[3].text(0.5, 0.5, 'No Probe Data Available', 
                        transform=axes[3].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
            axes[3].set_title('4. Probe BWE: Bandwidth Estimates by Cluster', 
                             fontsize=12, fontweight='bold')
            axes[3].grid(True, alpha=0.3)

        # 5. Final Decision Reasons
        if not decision_df.empty:
            decision_df['time_s'] = (decision_df['timestamp'] - start_time_ms) / 1000.0
            
            # Convert decision reasons to numeric for plotting
            reason_map = {
                'Hold': 0,           # Default state (lowest priority)
                'LossEstimate': 1,   # 4th priority: Loss-based BWE
                'ProbeResult': 2,    # 3rd priority: Probe results  
                'RttBackoff': 3,     # 2nd priority: RTT backoff
                'DelayLimit': 4      # 1st priority: Delay overuse (highest)
            }
            decision_df['decision_numeric'] = decision_df['decision_reason'].map(reason_map).fillna(0)
            
            # Create stepped plot for decision changes
            axes[4].step(decision_df['time_s'], decision_df['decision_numeric'], where='post', 
                         color='darkblue', linewidth=3, label='Final Decision')
            axes[4].fill_between(decision_df['time_s'], decision_df['decision_numeric'], alpha=0.3, 
                                 color='lightsteelblue', step='post')
            axes[4].set_ylabel('Decision Type', fontsize=11)
            axes[4].set_title('5. Final GCC Decision (Priority: DelayLimit > RTT > Probe > Loss)', 
                             fontsize=12, fontweight='bold')
            axes[4].set_yticks([0, 1, 2, 3, 4])
            axes[4].set_yticklabels(['Hold', 'Loss', 'Probe', 'RTT', 'DelayLimit'])
            axes[4].grid(True, alpha=0.3)
            
            # Add decision statistics
            decision_counts = decision_df['decision_reason'].value_counts()
            decision_text = ', '.join([f'{reason}: {count}' for reason, count in decision_counts.items()])
            axes[4].text(0.02, 0.95, f'Decisions: {decision_text}', transform=axes[4].transAxes, 
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5), fontsize=9)
            axes[4].legend(fontsize=10)

        # Set x-axis label only for the bottom subplot
        axes[4].set_xlabel('Time (seconds)', fontsize=12)
        
        # Set x-axis range for all subplots
        for ax in axes:
            ax.set_xlim(0, time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return fig

    def plot_constraint_analysis(self, data_dict):
        """
        Plot constraint analysis showing the 5-layer constraint application process.
        """
        constraint_df = data_dict.get('constraint_apply')
        delay_limit_df = data_dict.get('delay_limit')
        receiver_limit_df = data_dict.get('receiver_limit')
        pushback_df = data_dict.get('pushback')
        
        if constraint_df is None or constraint_df.empty:
            print("[!] No constraint application data found.")
            return None
        
        # Set matplotlib style
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            plt.style.use('default')
            
        # Create 6 vertical subplots for constraint analysis
        fig, axes = plt.subplots(6, 1, figsize=(16, 24), sharex=True)
        fig.suptitle(f'WebRTC GCC Constraint Analysis - 5-Layer Bandwidth Limitation\n({self.log_file_path})', 
                     fontsize=16, fontweight='bold')

        # Determine common time range
        if not constraint_df.empty:
            start_time_ms = constraint_df['timestamp'].min()
            end_time_ms = constraint_df['timestamp'].max()
            time_limit = (end_time_ms - start_time_ms) / 1000.0 + 1.0
            constraint_df['time_s'] = (constraint_df['timestamp'] - start_time_ms) / 1000.0
        else:
            return None

        # 1. Original LossBasedBwe Estimate
        axes[0].plot(constraint_df['time_s'], constraint_df['original']/1000, 'o-', 
                    color='green', label='LossBasedBwe Original', markersize=3, linewidth=2)
        axes[0].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[0].set_title('1. Original LossBasedBwe Estimate (Before Constraints)', 
                         fontsize=12, fontweight='bold')
        axes[0].grid(True, alpha=0.3)
        axes[0].legend(fontsize=10)

        # 2. DelayBased Constraint
        axes[1].plot(constraint_df['time_s'], constraint_df['delay_limit']/1000, 'o-', 
                    color='red', label='DelayBased Limit', markersize=3, linewidth=2)
        axes[1].plot(constraint_df['time_s'], constraint_df['original']/1000, '--', 
                    color='green', label='Original Estimate', alpha=0.7, linewidth=1)
        axes[1].fill_between(constraint_df['time_s'], constraint_df['delay_limit']/1000, 
                           constraint_df['original']/1000,
                           where=(constraint_df['delay_limit'] < constraint_df['original']),
                           color='red', alpha=0.3, label='DelayBased Constraint')
        axes[1].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[1].set_title('2. DelayBased Constraint Application (Highest Priority)', 
                         fontsize=12, fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        axes[1].legend(fontsize=10)

        # 3. Receiver Limit Constraint
        axes[2].plot(constraint_df['time_s'], constraint_df['receiver_limit']/1000, 'o-', 
                    color='orange', label='Receiver Limit', markersize=3, linewidth=2)
        axes[2].plot(constraint_df['time_s'], constraint_df['upper_limit']/1000, '--', 
                    color='purple', label='Combined Upper Limit', alpha=0.7, linewidth=1)
        axes[2].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[2].set_title('3. Receiver Limit Constraint', 
                         fontsize=12, fontweight='bold')
        axes[2].grid(True, alpha=0.3)
        axes[2].legend(fontsize=10)

        # 4. Config Limits (Min/Max)
        axes[3].plot(constraint_df['time_s'], constraint_df['max_config']/1000, 'o-', 
                    color='blue', label='Max Config Limit', markersize=3, linewidth=2)
        axes[3].plot(constraint_df['time_s'], constraint_df['min_config']/1000, 'o-', 
                    color='cyan', label='Min Config Limit', markersize=3, linewidth=2)
        axes[3].fill_between(constraint_df['time_s'], constraint_df['min_config']/1000, 
                           constraint_df['max_config']/1000,
                           color='lightblue', alpha=0.3, label='Config Range')
        axes[3].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[3].set_title('4. Configuration Limits (Min/Max Bitrate)', 
                         fontsize=12, fontweight='bold')
        axes[3].grid(True, alpha=0.3)
        axes[3].legend(fontsize=10)

        # 5. Pushback Effect (if data available)
        if pushback_df is not None and not pushback_df.empty:
            pushback_df['time_s'] = (pushback_df['timestamp'] - start_time_ms) / 1000.0
            axes[4].plot(pushback_df['time_s'], pushback_df['original_rate']/1000, 'o-', 
                        color='green', label='Before Pushback', markersize=3, linewidth=2)
            axes[4].plot(pushback_df['time_s'], pushback_df['pushback_rate']/1000, 'o-', 
                        color='red', label='After Pushback', markersize=3, linewidth=2)
            axes[4].fill_between(pushback_df['time_s'], pushback_df['pushback_rate']/1000, 
                               pushback_df['original_rate']/1000,
                               color='red', alpha=0.3, label='Pushback Reduction')
        else:
            axes[4].text(0.5, 0.5, 'No Congestion Window Pushback Data', 
                        transform=axes[4].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
        axes[4].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[4].set_title('5. Congestion Window Pushback Effect', 
                         fontsize=12, fontweight='bold')
        axes[4].grid(True, alpha=0.3)
        axes[4].legend(fontsize=10)

        # 6. Final Result Comparison
        axes[5].plot(constraint_df['time_s'], constraint_df['original']/1000, '--', 
                    color='green', label='Original LossBasedBwe', alpha=0.7, linewidth=2)
        axes[5].plot(constraint_df['time_s'], constraint_df['final']/1000, 'o-', 
                    color='purple', label='Final Constrained Rate', markersize=4, linewidth=3)
        axes[5].fill_between(constraint_df['time_s'], constraint_df['final']/1000, 
                           constraint_df['original']/1000,
                           where=(constraint_df['final'] < constraint_df['original']),
                           color='orange', alpha=0.3, label='Total Constraint Effect')
        axes[5].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[5].set_title('6. Final Constrained Bandwidth vs Original Estimate', 
                         fontsize=12, fontweight='bold')
        axes[5].set_xlabel('Time (seconds)', fontsize=12)
        axes[5].grid(True, alpha=0.3)
        axes[5].legend(fontsize=10)

        # Set x-axis range for all subplots
        for ax in axes:
            ax.set_xlim(0, time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return fig

def main():
    # Input log file path
    sender_log_file = 'sender_cloud.log' 
    
    try:
        analyzer = GccDecisionAnalyzer(sender_log_file)
        data_dict = analyzer.parse_log_file()
        
        # Plot original GCC decision metrics
        fig1 = analyzer.plot_gcc_decision_metrics(data_dict)
        
        # Plot new constraint analysis
        fig2 = analyzer.plot_constraint_analysis(data_dict)
        
        import os
        output_dir = 'analysis_results'
        os.makedirs(output_dir, exist_ok=True)
        
        if fig1:
            output_path1 = os.path.join(output_dir, 'gcc_decision_analysis_vertical.png')
            fig1.savefig(output_path1, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] Original decision chart saved to: {output_path1}")
            
        if fig2:
            output_path2 = os.path.join(output_dir, 'gcc_constraint_analysis.png')
            fig2.savefig(output_path2, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] Constraint analysis chart saved to: {output_path2}")

    except FileNotFoundError:
        print(f"[!] Error: File not found '{sender_log_file}'")
    except Exception as e:
        print(f"[!] Unknown error occurred while processing file: {e}")

if __name__ == "__main__":
    main()