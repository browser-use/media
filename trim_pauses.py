#!/usr/bin/env python3
"""
Trim pauses from video by detecting and cutting low-motion sequences.
Usage: trim_pauses.py video.mp4 start_sec end_sec [--motion-threshold 5.0] [--min-pause 1.0] [--keep-pause 0.2]
"""
import sys
import cv2
import subprocess
import numpy as np
from pathlib import Path
import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        description='Trim pauses from video by detecting low-motion frames',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s demo.mp4 4.25 50
  %(prog)s demo.mp4 0 60 --motion-threshold 8.0 --min-pause 2.0
  %(prog)s demo.mp4 10 30 --keep-pause 0.5 -o clean_demo.mp4
        """
    )
    parser.add_argument('video', help='Input video file (mp4)')
    parser.add_argument('start', type=float, help='Start timestamp in seconds')
    parser.add_argument('end', type=float, help='End timestamp in seconds')
    parser.add_argument('--motion-threshold', '-m', type=float, default=5.0,
                        help='Motion score threshold for detecting pauses (default: 5.0)')
    parser.add_argument('--min-pause', '-p', type=float, default=1.0,
                        help='Minimum pause duration in seconds to trim (default: 1.0)')
    parser.add_argument('--keep-pause', '-k', type=float, default=0.2,
                        help='Duration in seconds to keep from each pause (default: 0.2)')
    parser.add_argument('--output', '-o', help='Output file path (default: input_trimmed.mp4)')
    parser.add_argument('--preview', action='store_true',
                        help='Preview pause detection without processing')
    return parser.parse_args()

def frame_motion_score(frame1, frame2):
    """Calculate motion score between two frames using mean absolute difference."""
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    return np.mean(np.abs(gray1.astype(float) - gray2.astype(float)))

def analyze_motion(video_path, start_sec, end_sec):
    """Analyze motion between frames in the specified time range."""
    cap = cv2.VideoCapture(str(video_path))
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_sec * fps)
    end_frame = min(int(end_sec * fps), total_frames)
    
    if start_frame >= total_frames:
        raise ValueError(f"Start time {start_sec}s exceeds video duration")
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ret, prev_frame = cap.read()
    if not ret:
        raise ValueError("Failed to read first frame")
    
    scores = []
    frame_count = end_frame - start_frame - 1
    
    print(f"Analyzing {frame_count} frames ({(end_frame-start_frame)/fps:.2f}s) at {fps:.1f} fps...")
    
    for i in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break
        scores.append(frame_motion_score(prev_frame, frame))
        prev_frame = frame
        
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{frame_count} frames ({100*(i+1)/frame_count:.1f}%)", end='\r')
    
    print(f"  Processed {len(scores)}/{frame_count} frames (100.0%)    ")
    cap.release()
    
    return scores, fps, start_frame

def print_motion_statistics(scores, current_threshold):
    """Print statistics about motion scores to help tune the threshold."""
    scores_array = np.array(scores)
    
    print("\nMotion Score Statistics:")
    print(f"  Count:      {len(scores):,} frames")
    print(f"  Mean:       {np.mean(scores_array):.2f}")
    print(f"  Median:     {np.median(scores_array):.2f}")
    print(f"  Std Dev:    {np.std(scores_array):.2f}")
    print(f"  Min:        {np.min(scores_array):.2f}")
    print(f"  Max:        {np.max(scores_array):.2f}")
    
    print("\nPercentiles:")
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        value = np.percentile(scores_array, p)
        print(f"  {p:2d}th:      {value:.5f}")
    
    below_threshold = np.sum(scores_array < current_threshold)
    pct_below = 100 * below_threshold / len(scores)
    print(f"\nFrames below threshold ({current_threshold:.1f}):")
    print(f"  {below_threshold:,} frames ({pct_below:.1f}%)")
    
    print("\nDistribution (histogram):")
    bins = [0, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, np.inf]
    labels = ['0-0.00005', '0.00005-0.0001', '0.0001-0.0005', '0.0005-0.001', '0.001-0.005', '0.005-0.01', '0.01-0.05', '0.05-0.1', '0.1-0.5', '0.5-1.0', '1.0+']
    hist, _ = np.histogram(scores_array, bins=bins)
    
    for label, count in zip(labels, hist):
        pct = 100 * count / len(scores)
        bar_width = int(pct / 2)
        bar = '█' * bar_width
        print(f"  {label:>8}: {count:6,} ({pct:5.1f}%) {bar}")

def detect_pauses(scores, motion_threshold, min_pause_frames):
    """Detect pause ranges where motion is below threshold for minimum duration."""
    pauses = []
    in_pause = False
    pause_start = 0
    
    for i, score in enumerate(scores):
        if score < motion_threshold and not in_pause:
            in_pause = True
            pause_start = i
        elif score >= motion_threshold and in_pause:
            pause_len = i - pause_start
            if pause_len >= min_pause_frames:
                pauses.append((pause_start, i, pause_len))
            in_pause = False
    
    if in_pause and len(scores) - pause_start >= min_pause_frames:
        pauses.append((pause_start, len(scores), len(scores) - pause_start))
    
    return pauses

def build_keep_ranges(pauses, total_frames, keep_frames, start_offset):
    """Build list of frame ranges to keep after trimming pauses."""
    keep_ranges = []
    last_frame = 0
    
    for pause_start, pause_end, pause_len in pauses:
        if pause_start > last_frame:
            keep_ranges.append((last_frame + start_offset, pause_start - 1 + start_offset))
        
        if keep_frames > 0:
            keep_end = min(pause_start + keep_frames - 1, pause_end - 1)
            keep_ranges.append((pause_start + start_offset, keep_end + start_offset))
        
        last_frame = pause_end
    
    if last_frame < total_frames:
        keep_ranges.append((last_frame + start_offset, total_frames - 1 + start_offset))
    
    return keep_ranges

def trim_video(video_path, keep_ranges, output_path):
    """Use ffmpeg to extract and concatenate frame ranges."""
    filter_parts = [f"between(n,{start},{end})" for start, end in keep_ranges]
    filter_expr = '+'.join(filter_parts)
    
    print(f"\nProcessing video with ffmpeg...")
    result = subprocess.run(
        ['ffmpeg', '-i', str(video_path), 
         '-vf', f"select='{filter_expr}',setpts=N/FRAME_RATE/TB",
         '-af', f"aselect='{filter_expr}',asetpts=N/SR/TB",
         '-y', str(output_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

def main():
    args = parse_args()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    print(f"Video: {video_path.name}")
    print(f"Time range: {args.start}s - {args.end}s")
    print(f"Motion threshold: {args.motion_threshold}")
    
    scores, fps, start_frame = analyze_motion(video_path, args.start, args.end)
    
    print_motion_statistics(scores, args.motion_threshold)
    
    min_pause_frames = int(args.min_pause * fps)
    keep_pause_frames = int(args.keep_pause * fps)
    
    pauses = detect_pauses(scores, args.motion_threshold, min_pause_frames)
    
    if not pauses:
        print("\nNo pauses detected!")
        return
    
    total_pause_time = sum(p[2] for p in pauses) / fps
    trimmed_time = sum(max(0, p[2] - keep_pause_frames) for p in pauses) / fps
    
    print(f"\nDetected {len(pauses)} pause(s):")
    for i, (ps, pe, plen) in enumerate(pauses, 1):
        time_start = (ps + start_frame) / fps
        duration = plen / fps
        print(f"  {i}. {time_start:.2f}s - {time_start + duration:.2f}s ({duration:.2f}s)")
    
    print(f"\nTotal pause time: {total_pause_time:.2f}s")
    print(f"Will trim: {trimmed_time:.2f}s")
    print(f"Result: {(args.end - args.start) - trimmed_time:.2f}s")
    
    if args.preview:
        print("\nPreview mode - no video processing")
        return
    
    output_path = Path(args.output) if args.output else video_path.with_stem(f"{video_path.stem}_trimmed")
    keep_ranges = build_keep_ranges(pauses, len(scores), keep_pause_frames, start_frame)
    
    trim_video(video_path, keep_ranges, output_path)
    
    print(f"\nDone! Saved to: {output_path.name}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
