# Browser Use Media

Repository for hosting video demos and other media assets to embed in documentation and related materials.

http://docs.browser-use.com

## Tools

### trim_pauses.py

Intelligently trims pauses from video by detecting low-motion sequences and cutting them down. Perfect for cleaning up demo recordings with long pauses.

**Basic usage:**
```bash
python trim_pauses.py video.mp4 4.25 50
```

**With options:**
```bash
python trim_pauses.py demo.mp4 0 60 --motion-threshold 8.0 --min-pause 2.0 --keep-pause 0.5 -o clean.mp4
```

**Preview mode** (detect pauses without processing):
```bash
python trim_pauses.py video.mp4 10 30 --preview
```

**Options:**
- `--motion-threshold, -m`: Motion score threshold for detecting pauses (default: 5.0)
  - Lower values = more sensitive (detects smaller movements as non-pauses)
  - Higher values = less sensitive (only very still frames count as pauses)
- `--min-pause, -p`: Minimum pause duration in seconds to trim (default: 1.0)
- `--keep-pause, -k`: Duration in seconds to keep from each pause (default: 0.2)
- `--output, -o`: Output file path (default: input_trimmed.mp4)
- `--preview`: Preview pause detection without processing video

**How it works:**
1. Analyzes frames between start and end timestamps
2. Calculates motion score between consecutive frames
3. Identifies pauses where motion stays below threshold
4. Trims pauses longer than minimum duration down to keep duration
5. Uses ffmpeg to create the trimmed output

**Tips:**
- Use `--preview` to experiment with threshold values before processing
- Adjust `--motion-threshold` based on video content (static screen vs. animated UI)
- Set `--keep-pause 0` to completely remove pauses