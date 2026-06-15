# Beamer Presentation

Presentation, designed for about 20 minutes, of the HAL ACENTAURI HCERES POC.

Compile:

```bash
cd presentation
pdflatex hal_acentauri_hceres_poc_presentation.tex
```

Generate a narrated video from the compiled PDF:

```bash
cd presentation
python3 generate_narrated_video.py
```

This uses `edge-tts` for neural narration and local tools `pdftoppm`,
`ffmpeg`, and `ffprobe`. The video starts with a generated title card,
uses slowed-down text-to-speech narration, matches each slide duration to
its audio, and compresses long text-to-speech silences. Audio generation
requires network access.
The generated MP4 is:

```text
hal_acentauri_hceres_poc_presentation_narrated.mp4
```

The source file contains 15 slides:

1. Title and 20-minute presentation outline
2. Problem addressed
3. Proposed idea
4. How AI agents were used
5. Framing prompt given to the AI
6. Implementation
7. Generated artifacts
8. Inside the deterministic report
9. Results obtained
10. Demonstration
11. Narrated video synchronization
12. Limitations and next steps
13. Self-assessment: AI time saved
14. Conclusion
15. How this video was generated
