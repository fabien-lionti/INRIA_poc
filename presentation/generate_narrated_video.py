# # #!/usr/bin/env python3
# # """Generate a narrated MP4 video from the Beamer PDF presentation.

# # The script uses local command-line tools only:
# # - pdftoppm to render slides as PNG images;
# # - ffmpeg/ffprobe to compose the final video.

# # It uses edge-tts for narration, which requires network access when generating
# # audio.
# # """

# # from __future__ import annotations

# # import asyncio
# # import re
# # import shutil
# # import subprocess
# # import sys
# # from pathlib import Path

# # import edge_tts


# # ROOT = Path(__file__).resolve().parent
# # PDF = ROOT / "hal_acentauri_hceres_poc_presentation.pdf"
# # BUILD = ROOT / "video_build"
# # FRAMES = BUILD / "frames"
# # AUDIO = BUILD / "audio"
# # CLIPS = BUILD / "clips"
# # TITLE_CARD = BUILD / "title_card.png"
# # OUTPUT = ROOT / "hal_acentauri_hceres_poc_presentation_narrated.mp4"
# # VOICE = "en-US-GuyNeural"
# # VOICE_RATE = "-15%"
# # AUDIO_SAMPLE_RATE = "48000"
# # AUDIO_CHANNELS = "2"
# # AUDIO_BITRATE = "128k"
# # TITLE_TEXT = "HAL ACENTAURI HCERES POC"
# # TITLE_SUBTEXT = "Narrated presentation"
# # TITLE_NARRATION = "HAL ACENTAURI HCERES proof of concept. Narrated presentation."
# # TITLE_DURATION_PAD = 0.5
# # FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# # FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# # SILENCE_FILTER = (
# #     "silenceremove="
# #     "start_periods=1:start_duration=0.05:start_threshold=-35dB:start_silence=0.08:"
# #     "stop_periods=-1:stop_duration=0.75:stop_threshold=-35dB:stop_silence=0.25"
# # )


# # NARRATION = [
# #     """
# #     HAL ACENTAURI HCERES proof of concept.
# #     This presentation explains a reproducible bibliometric analysis pipeline for
# #     preparing an HCERES-style evaluation. The presentation covers the problem,
# #     the proposed idea, the use of AI agents, the implementation, the generated
# #     report, the results, a short demonstration path, video generation, and a
# #     self-assessment of time saved.
# #     """,
# #     """
# #     The problem addressed is an evaluation preparation bottleneck.
# #     Preparing an HCERES-style evaluation requires a reliable synthesis of
# #     scientific output, collaborations, publication venues, and open science
# #     indicators. Most data exists in HAL, but the metadata is heterogeneous and
# #     sometimes incomplete. Manual extraction is repetitive, hard to audit, and
# #     easy to make inconsistent. The goal is to accelerate and structure expert
# #     validation, not to replace it.
# #     """,
# #     """
# #     The proposed idea is to build a local, deterministic, and rerunnable
# #     pipeline. The inputs are a HAL query or structure identifier, an analysis
# #     period, and optional CSV files for members, themes, Scimago, and CORE.
# #     The outputs are CSV tables, LaTeX tables, figures, a Markdown report, and a
# #     standalone LaTeX report.
# #     """,
# #     """
# #     AI agents were used throughout the project. ChatGPT supported clarification,
# #     design discussion, and text drafting. Codex supported code generation,
# #     repository edits, debugging, tests, documentation, and slides. Paid AI APIs
# #     were used during development and material preparation. The human role remains
# #     essential: define the institutional need, check assumptions, validate
# #     outputs, and decide what is reliable enough for HCERES use.
# #     """,
# #     """
# #     The framing prompt asked for a simple, monolithic Python proof of concept to
# #     automate a HAL-based bibliometric analysis of the ACENTAURI team, in a
# #     format useful for HCERES preparation. The expected behavior included HAL
# #     querying, cleaning, filtering, deduplication, computation of indicators,
# #     optional CSV enrichments, and deterministic reporting with explicit
# #     provenance and no invented content.
# #     """,
# #     """
# #     The implementation starts by discovering the HAL query or using an explicit
# #     structure identifier. It retrieves HAL records through paginated API calls,
# #     normalizes metadata, filters out non-target records, deduplicates
# #     publications, identifies ACENTAURI members, computes indicators, and exports
# #     deliverables. A key design principle is to distinguish verified HAL metadata,
# #     inferred information, manually supplied data, and unavailable information.
# #     """,
# #     """
# #     The generated artifacts include a single Python module,
# #     hal_acentauri_hceres_poc.py, command-line options for period, team, output
# #     directory, and optional CSV files, static smoke tests, documentation, and
# #     example CSV files. Generated outputs include CSV and LaTeX tables, figures,
# #     collaboration network exports, a Markdown report, and a standalone LaTeX
# #     report. The pipeline can be rerun locally.
# #     """,
# #     """
# #     The deterministic report is assembled from computed indicators and explicit
# #     metadata provenance. It includes the analysis scope, the team name, the
# #     period, the HAL query, the number of raw HAL records, and the number of
# #     publications retained. It also contains audit-oriented sections such as top
# #     authors, venues, collaboration patterns, open science indicators, missing
# #     optional data, validation needs, and limitations. For example, it states that
# #     theme attribution is reliable only for authors present in the theme mapping
# #     CSV or otherwise discoverable from metadata.
# #     """,
# #     """
# #     The existing run retrieved sixty-nine HAL records. After filtering, it kept
# #     fifty-eight publications and identified or inferred thirty-one members. It
# #     generated Markdown, LaTeX, and PDF reports. Open science indicators showed
# #     fifty-six publications with full text in HAL, two without full text,
# #     twenty-four with DOI, fifty-five English publications, and three French
# #     publications. These numbers are a first audit basis, not a final
# #     institutional validation.
# #     """,
# #     """
# #     The demonstration path is straightforward. First, run the pipeline with
# #     python hal_acentauri_hceres_poc.py, using the outputs directory. Then inspect
# #     outputs slash reports slash hceres_summary_report dot md. Next, open the
# #     generated LaTeX tables and figures. Finally, explain how optional enrichment
# #     files such as acentauri_members, theme_mapping, scimago_journals, and
# #     core_conferences enter the workflow.
# #     """,
# #     """
# #     The narrated video is synchronized at the level of each slide. Each slide has
# #     a dedicated narration paragraph. The script uses the audio duration to keep
# #     each slide on screen for the right amount of time, slows down the text to
# #     speech voice, compresses long silences, and inserts a title card before the
# #     slide sequence. Codex created the script, adjusted the voice, compressed
# #     silences, and regenerated the final MP4.
# #     """,
# #     """
# #     The main limitations are incomplete or heterogeneous HAL metadata, partly
# #     inferred member identification when no validated CSV is provided, missing
# #     ARC, RIC, and MOC theme mapping, and heuristic partner classification. The
# #     next steps are to validate the member list, provide theme mapping, add
# #     Scimago and CORE reference data, and add domain-level quality control before
# #     institutional use.
# #     """,
# #     """
# #     The self-assessment estimates the use of ChatGPT and Codex. AI supported
# #     idea structuring, implementation, debugging, tests, documentation, report
# #     generation, slide drafting, and video generation. Estimated time without AI
# #     was more than one week, estimated at more than forty hours. Estimated time
# #     with AI was about three hours. The estimated time saved was more than
# #     thirty-seven hours, or several working days. AI worked well for the first
# #     end-to-end implementation, documentation, slides, and narrated video, but
# #     human validation was still required for institutional meaning and final
# #     quality control.
# #     """,
# #     """
# #     In conclusion, the main contribution is a reproducible proof of concept that
# #     turns HAL metadata into a first HCERES-oriented analysis package. It produces
# #     tables, figures, report files, and explicit validation gaps. The project
# #     demonstrates how AI agents can accelerate practical research administration
# #     tooling, while keeping the generated pipeline deterministic and auditable.
# #     """,
# #     """
# #     This final slide explains how the video itself was generated. The Beamer
# #     source was compiled to PDF with pdflatex. Each PDF page was rendered as a PNG
# #     image with pdftoppm. Edge text to speech generated one audio file per slide.
# #     FFmpeg compressed long silences, created one still image video clip per slide,
# #     matched each clip duration to its narration, and concatenated everything into
# #     the final MP4. The result contains a title card, narrated slides, slower
# #     speech, and no detected silences longer than one second.
# #     """,
# # ]


# # def run(command: list[str]) -> None:
# #     print("+", " ".join(command))
# #     subprocess.run(command, check=True)


# # def require_tool(name: str) -> None:
# #     if shutil.which(name) is None:
# #         raise SystemExit(f"Missing required tool: {name}")


# # async def synthesize_speech(text: str, output_path: Path) -> None:
# #     communicate = edge_tts.Communicate(normalize_narration(text), VOICE, rate=VOICE_RATE)
# #     await communicate.save(str(output_path))


# # def normalize_narration(text: str) -> str:
# #     """Avoid unintended TTS pauses from line wrapping and technical notation."""
# #     text = re.sub(r"\s+", " ", text).strip()
# #     replacements = {
# #         "HCERES-style": "HCERES style",
# #         "HAL-based": "HAL based",
# #         "audit-oriented": "audit oriented",
# #         "end-to-end": "end to end",
# #         "edge TTS": "Edge text to speech",
# #         "edge-tts": "Edge text to speech",
# #         "ffmpeg": "F Fmpeg",
# #         "ffprobe": "F Fprobe",
# #         "Scimago": "SCImago",
# #         "ACENTAURI": "Acentauri",
# #     }
# #     for old, new in replacements.items():
# #         text = text.replace(old, new)
# #     return text


# # def audio_duration(path: Path) -> float:
# #     result = subprocess.run(
# #         [
# #             "ffprobe",
# #             "-v",
# #             "error",
# #             "-show_entries",
# #             "format=duration",
# #             "-of",
# #             "default=noprint_wrappers=1:nokey=1",
# #             str(path),
# #         ],
# #         check=True,
# #         text=True,
# #         capture_output=True,
# #     )
# #     return float(result.stdout.strip())


# # def compress_silences(source_path: Path, output_path: Path) -> None:
# #     run(
# #         [
# #             "ffmpeg",
# #             "-y",
# #             "-i",
# #             str(source_path),
# #             "-af",
# #             f"{SILENCE_FILTER},aresample={AUDIO_SAMPLE_RATE}:async=1000:first_pts=0",
# #             "-ar",
# #             AUDIO_SAMPLE_RATE,
# #             "-ac",
# #             AUDIO_CHANNELS,
# #             str(output_path),
# #         ]
# #     )


# # def create_title_card() -> None:
# #     run(
# #         [
# #             "ffmpeg",
# #             "-y",
# #             "-f",
# #             "lavfi",
# #             "-i",
# #             "color=c=0x164194:s=1920x1080:d=1",
# #             "-vf",
# #             (
# #                 f"drawtext=fontfile={FONT_BOLD}:text='{TITLE_TEXT}':"
# #                 "fontcolor=white:fontsize=70:x=(w-text_w)/2:y=390,"
# #                 f"drawtext=fontfile={FONT_REGULAR}:text='{TITLE_SUBTEXT}':"
# #                 "fontcolor=white:fontsize=34:x=(w-text_w)/2:y=500"
# #             ),
# #             "-frames:v",
# #             "1",
# #             str(TITLE_CARD),
# #         ]
# #     )


# # def create_clip(frame: Path, audio_path: Path, duration: float, output_path: Path) -> None:
# #     run(
# #         [
# #             "ffmpeg",
# #             "-y",
# #             "-loop",
# #             "1",
# #             "-framerate",
# #             "30",
# #             "-i",
# #             str(frame),
# #             "-i",
# #             str(audio_path),
# #             "-t",
# #             f"{duration:.3f}",
# #             "-vf",
# #             "scale=1920:-2,format=yuv420p",
# #             "-c:v",
# #             "libx264",
# #             "-preset",
# #             "veryfast",
# #             "-tune",
# #             "stillimage",
# #             "-c:a",
# #             "aac",
# #             "-ar",
# #             AUDIO_SAMPLE_RATE,
# #             "-ac",
# #             AUDIO_CHANNELS,
# #             "-b:a",
# #             AUDIO_BITRATE,
# #             "-shortest",
# #             str(output_path),
# #         ]
# #     )


# # def concatenate_clips(clip_paths: list[Path]) -> None:
# #     command = ["ffmpeg", "-y"]
# #     for path in clip_paths:
# #         command.extend(["-i", str(path)])

# #     normalized_streams: list[str] = []
# #     concat_inputs: list[str] = []
# #     for index in range(len(clip_paths)):
# #         normalized_streams.append(
# #             f"[{index}:v:0]scale=1920:1080,setsar=1[v{index}];"
# #             f"[{index}:a:0]aformat=sample_rates={AUDIO_SAMPLE_RATE}:channel_layouts=stereo[a{index}]"
# #         )
# #         concat_inputs.append(f"[v{index}][a{index}]")
# #     filter_complex = (
# #         ";".join(normalized_streams)
# #         + ";"
# #         + "".join(concat_inputs)
# #         + f"concat=n={len(clip_paths)}:v=1:a=1[v][a]"
# #     )
# #     command.extend(
# #         [
# #             "-filter_complex",
# #             filter_complex,
# #             "-map",
# #             "[v]",
# #             "-map",
# #             "[a]",
# #             "-c:v",
# #             "libx264",
# #             "-preset",
# #             "veryfast",
# #             "-pix_fmt",
# #             "yuv420p",
# #             "-r",
# #             "30",
# #             "-c:a",
# #             "aac",
# #             "-ar",
# #             AUDIO_SAMPLE_RATE,
# #             "-ac",
# #             AUDIO_CHANNELS,
# #             "-b:a",
# #             AUDIO_BITRATE,
# #             "-movflags",
# #             "+faststart",
# #             str(OUTPUT),
# #         ]
# #     )
# #     run(command)


# # def existing_clip_paths() -> list[Path]:
# #     return [CLIPS / "title.mp4", *sorted(CLIPS.glob("slide_*.mp4"))]


# # def main() -> None:
# #     for tool in ["pdftoppm", "ffmpeg", "ffprobe"]:
# #         require_tool(tool)
# #     if not PDF.exists():
# #         raise SystemExit(f"Missing PDF: {PDF}")

# #     if "--concat-only" in sys.argv:
# #         clip_paths = existing_clip_paths()
# #         if len(clip_paths) != len(NARRATION) + 1 or any(not path.exists() for path in clip_paths):
# #             raise SystemExit("Missing generated clips; run the full generator first.")
# #         concatenate_clips(clip_paths)
# #         print(f"Generated {OUTPUT}")
# #         return

# #     if BUILD.exists():
# #         shutil.rmtree(BUILD)
# #     FRAMES.mkdir(parents=True)
# #     AUDIO.mkdir(parents=True)
# #     CLIPS.mkdir(parents=True)

# #     run(["pdftoppm", "-png", "-r", "180", str(PDF), str(FRAMES / "slide")])
# #     frame_paths = sorted(FRAMES.glob("slide-*.png"))
# #     if len(frame_paths) != len(NARRATION):
# #         raise SystemExit(
# #             f"Expected {len(NARRATION)} slide images, got {len(frame_paths)}"
# #         )

# #     clip_paths: list[Path] = []

# #     create_title_card()
# #     raw_title_audio = AUDIO / "title_raw.mp3"
# #     title_audio = AUDIO / "title.wav"
# #     title_clip = CLIPS / "title.mp4"
# #     print(f"Synthesizing title card with {VOICE}")
# #     asyncio.run(synthesize_speech(TITLE_NARRATION, raw_title_audio))
# #     compress_silences(raw_title_audio, title_audio)
# #     title_duration = audio_duration(title_audio) + TITLE_DURATION_PAD
# #     create_clip(TITLE_CARD, title_audio, title_duration, title_clip)
# #     clip_paths.append(title_clip)

# #     for index, (frame, narration) in enumerate(zip(frame_paths, NARRATION), start=1):
# #         raw_audio_path = AUDIO / f"slide_{index:02d}_raw.mp3"
# #         audio_path = AUDIO / f"slide_{index:02d}.wav"
# #         clip_path = CLIPS / f"slide_{index:02d}.mp4"
# #         print(f"Synthesizing slide {index:02d} with {VOICE}")
# #         asyncio.run(synthesize_speech(narration, raw_audio_path))
# #         compress_silences(raw_audio_path, audio_path)
# #         duration = audio_duration(audio_path)
# #         create_clip(frame, audio_path, duration, clip_path)
# #         clip_paths.append(clip_path)

# #     concatenate_clips(clip_paths)
# #     print(f"Generated {OUTPUT}")


# # if __name__ == "__main__":
# #     main()

# #!/usr/bin/env python3
# """Generate a narrated MP4 video from the Beamer PDF presentation.

# The script uses local command-line tools only:
# - pdftoppm to render slides as PNG images;
# - ffmpeg/ffprobe to compose the final video.

# It uses edge-tts for narration, which requires network access when generating
# audio.
# """

# from __future__ import annotations

# import asyncio
# import re
# import shutil
# import subprocess
# import sys
# from pathlib import Path

# import edge_tts


# ROOT = Path(__file__).resolve().parent
# PDF = ROOT / "hal_acentauri_hceres_poc_presentation.pdf"
# BUILD = ROOT / "video_build"
# FRAMES = BUILD / "frames"
# AUDIO = BUILD / "audio"
# CLIPS = BUILD / "clips"
# TITLE_CARD = BUILD / "title_card.png"
# OUTPUT = ROOT / "hal_acentauri_hceres_poc_presentation_narrated.mp4"

# # ---------------------------------------------------------------------
# # Voice and audio parameters
# # ---------------------------------------------------------------------

# VOICE = "en-US-GuyNeural"

# # Slower narration.
# # Try "-25%" if "-30%" feels too slow.
# # Try "-35%" if you still find it too fast.
# VOICE_RATE = "-20%"

# AUDIO_SAMPLE_RATE = "48000"
# AUDIO_CHANNELS = "2"
# AUDIO_BITRATE = "128k"

# TITLE_TEXT = "HAL ACENTAURI HCERES POC"
# TITLE_SUBTEXT = "Narrated presentation"
# TITLE_NARRATION = "HAL ACENTAURI HCERES proof of concept. Narrated presentation."

# # Extra breathing time after the title card.
# TITLE_DURATION_PAD = 1.0

# # Extra breathing time after each slide narration.
# SLIDE_DURATION_PAD = 0.8

# FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# NARRATION = [
#     """
#     This presentation introduces a reproducible bibliometric analysis pipeline
#     designed to support HCERES-style evaluation preparation for the ACENTAURI
#     team. The main idea is not to automate the evaluation itself, but to generate
#     a verifiable working basis for expert validation. The presentation covers the
#     problem, the proposed solution, the use of AI agents, the implementation
#     pipeline, the generated artifacts, the first results, the demonstration path,
#     the narrated video generation process, the limitations, and a final
#     self-assessment.
#     """,

#     """
#     The problem addressed is an evaluation preparation bottleneck. Preparing an
#     HCERES-style evaluation requires a reliable synthesis of publications,
#     collaborations, venues, open-science indicators, and validation gaps. Most of
#     the source data exists in HAL, but the metadata is heterogeneous and
#     sometimes incomplete. Manual extraction is slow, repetitive, difficult to
#     audit, and prone to inconsistencies. The goal is therefore to accelerate and
#     structure expert validation, not to replace it.
#     """,

#     """
#     The proposed solution is a local, deterministic, and rerunnable pipeline. The
#     inputs are HAL metadata and optional CSV files, such as member lists, theme
#     mappings, Scimago data, or CORE conference rankings. The central component is
#     a monolithic Python proof of concept called hal_acentauri_hceres_poc.py. The
#     outputs are tables, figures, collaboration network exports, and report files.
#     Optional CSV files enrich or correct the analysis, but they are not required
#     for the pipeline to run.
#     """,

#     """
#     AI agents were used as development accelerators. The workflow started from a
#     human need: preparing a reliable HCERES-oriented analysis. ChatGPT helped
#     clarify the need, structure the ideas, and draft explanatory material. Codex
#     helped generate and modify the code, debug the repository, add tests,
#     improve documentation, and prepare the slides and video scripts. The
#     important point is that AI remains inside a validation loop. The institutional
#     interpretation and final quality control remain human responsibilities.
#     """,

#     """
#     The initial prompt asked for a simple, monolithic Python proof of concept to
#     automate a HAL-based bibliometric analysis of the ACENTAURI team in a format
#     useful for HCERES-style preparation. The expected behavior included querying
#     HAL, cleaning metadata, filtering non-target records, deduplicating
#     publications, computing indicators, accepting optional CSV enrichments, and
#     generating deterministic reports with explicit provenance and no invented
#     content.
#     """,

#     """
#     The implementation pipeline follows six main steps. First, it discovers the
#     HAL query or uses an explicit structure identifier. Second, it retrieves HAL
#     records through paginated API calls. Third, it normalizes metadata such as
#     titles, authors, dates, document types, affiliations, DOI information, and
#     files. Fourth, it filters and deduplicates the records. Fifth, it computes
#     indicators. Sixth, it exports the generated artifacts. The useful part is not
#     only the final report, but the auditable path from HAL metadata to each
#     indicator.
#     """,

#     """
#     The pipeline explicitly distinguishes different levels of provenance and
#     trust. Some information comes from verified HAL metadata. Some information is
#     inferred, for example when identifying recurrent authors. Some information
#     can be manually supplied through CSV files, such as validated members or
#     theme mappings. Some information remains missing or unavailable. The report
#     exposes these categories instead of hiding uncertainty, which is essential
#     for institutional use.
#     """,

#     """
#     The generated artifacts include repository deliverables and output files. On
#     the repository side, there is a single Python module, command-line options
#     for the period, team, output directory, and optional CSV files, static smoke
#     tests, documentation, and example CSV files. On the output side, the pipeline
#     generates CSV tables, LaTeX tables, figures, collaboration network exports, a
#     Markdown summary report, and a standalone LaTeX report. The pipeline can be
#     rerun locally.
#     """,

#     """
#     The deterministic report is not free-form text invented by a language model.
#     It is assembled from computed indicators, explicit metadata provenance, and
#     known validation gaps. It includes the analysis scope, the team name, the
#     period, the HAL query, the number of raw HAL records, and the number of
#     retained publications. It also includes audit-oriented sections such as top
#     authors, venues, collaboration patterns, open-science indicators, missing
#     optional data, limitations, and validation needs.
#     """,

#     """
#     In the existing run, the pipeline retrieved sixty-nine HAL records. After
#     filtering, it retained fifty-eight publications and identified or inferred
#     thirty-one members. It generated Markdown, LaTeX, and PDF reports. The
#     open-science indicators showed fifty-six publications with full text in HAL,
#     two without full text, twenty-four publications with DOI, fifty-five English
#     publications, and three French publications. These numbers provide a first
#     audit basis, not a final institutional validation.
#     """,

#     """
#     The demonstration path is straightforward. First, run the pipeline with
#     python hal_acentauri_hceres_poc.py and select the output directory. Then
#     inspect the generated Markdown report in outputs slash reports slash
#     hceres_summary_report dot md. Next, open the generated LaTeX tables and
#     figures. Finally, explain where optional enrichment files enter the workflow,
#     such as acentauri_members, theme_mapping, scimago_journals, and
#     core_conferences.
#     """,

#     """
#     The narrated video is synchronized at the level of each slide. Each slide has
#     a dedicated narration paragraph. The script uses the generated audio duration
#     to keep each slide on screen for the right amount of time. The text-to-speech
#     voice is slowed down to improve comprehension. Long silences are compressed
#     to avoid empty waiting time, and a title card is inserted before the slide
#     sequence. Codex helped create the script, adjust the voice speed, compress
#     silences, and regenerate the final MP4.
#     """,

#     """
#     The video generation process starts from the Beamer source and the narration
#     script. The Beamer source is compiled to PDF with pdflatex. Each PDF page is
#     rendered as a PNG image with pdftoppm. Then edge-tts generates one audio
#     narration file per slide. FFmpeg is used to process the audio, compress long
#     silences, create one still-image video clip per slide, match each clip
#     duration to its narration, and concatenate all clips into the final MP4. The
#     result is a narrated video with synchronized slides and more natural pacing.
#     """,

#     """
#     The main limitations are incomplete or heterogeneous HAL metadata, partly
#     inferred member identification when no validated CSV is provided, missing
#     ARC, RIC, and MOC theme mapping, and heuristic partner classification. The
#     next steps are to validate the member list, provide theme mapping, add
#     Scimago and CORE reference data, and add domain-level quality control before
#     institutional use. The key conclusion is that AI accelerates implementation,
#     deterministic processing makes outputs reproducible, and human validation
#     gives the result institutional value.
#     """,

#     """
#     The final slide gives a self-assessment of the AI-assisted workflow. ChatGPT
#     and Codex supported idea structuring, implementation, debugging, tests,
#     documentation, report generation, slide drafting, and video generation.
#     Without AI, this work was estimated to take more than one week, or more than
#     forty hours. With AI, the estimated time was about three hours. The estimated
#     time saved was therefore more than thirty-seven hours, or several working
#     days. The final message is that AI can accelerate practical research
#     administration tooling, but the generated outputs must remain deterministic,
#     auditable, and validated by humans.
#     """,
# ]


# def run(command: list[str]) -> None:
#     print("+", " ".join(command))
#     subprocess.run(command, check=True)


# def require_tool(name: str) -> None:
#     if shutil.which(name) is None:
#         raise SystemExit(f"Missing required tool: {name}")


# async def synthesize_speech(text: str, output_path: Path) -> None:
#     communicate = edge_tts.Communicate(
#         normalize_narration(text),
#         VOICE,
#         rate=VOICE_RATE,
#     )
#     await communicate.save(str(output_path))


# def normalize_narration(text: str) -> str:
#     """Avoid unintended TTS pauses from line wrapping and technical notation."""
#     text = re.sub(r"\s+", " ", text).strip()
#     replacements = {
#         "HCERES-style": "HCERES style",
#         "HAL-based": "HAL based",
#         "audit-oriented": "audit oriented",
#         "end-to-end": "end to end",
#         "edge TTS": "Edge text to speech",
#         "edge-tts": "Edge text to speech",
#         "ffmpeg": "F Fmpeg",
#         "ffprobe": "F Fprobe",
#         "Scimago": "SCImago",
#         "ACENTAURI": "Acentauri",
#     }
#     for old, new in replacements.items():
#         text = text.replace(old, new)
#     return text


# def audio_duration(path: Path) -> float:
#     result = subprocess.run(
#         [
#             "ffprobe",
#             "-v",
#             "error",
#             "-show_entries",
#             "format=duration",
#             "-of",
#             "default=noprint_wrappers=1:nokey=1",
#             str(path),
#         ],
#         check=True,
#         text=True,
#         capture_output=True,
#     )
#     return float(result.stdout.strip())


# def compress_silences(source_path: Path, output_path: Path) -> None:
#     """Normalize audio format without aggressively removing silences.

#     The function name is kept for compatibility with the rest of the script,
#     but it no longer removes silences. This avoids choppy or unnatural narration.
#     """
#     run(
#         [
#             "ffmpeg",
#             "-y",
#             "-i",
#             str(source_path),
#             "-af",
#             f"aresample={AUDIO_SAMPLE_RATE}:async=1000:first_pts=0",
#             "-ar",
#             AUDIO_SAMPLE_RATE,
#             "-ac",
#             AUDIO_CHANNELS,
#             str(output_path),
#         ]
#     )


# def create_title_card() -> None:
#     run(
#         [
#             "ffmpeg",
#             "-y",
#             "-f",
#             "lavfi",
#             "-i",
#             "color=c=0x164194:s=1920x1080:d=1",
#             "-vf",
#             (
#                 f"drawtext=fontfile={FONT_BOLD}:text='{TITLE_TEXT}':"
#                 "fontcolor=white:fontsize=70:x=(w-text_w)/2:y=390,"
#                 f"drawtext=fontfile={FONT_REGULAR}:text='{TITLE_SUBTEXT}':"
#                 "fontcolor=white:fontsize=34:x=(w-text_w)/2:y=500"
#             ),
#             "-frames:v",
#             "1",
#             str(TITLE_CARD),
#         ]
#     )


# def create_clip(frame: Path, audio_path: Path, duration: float, output_path: Path) -> None:
#     run(
#         [
#             "ffmpeg",
#             "-y",
#             "-loop",
#             "1",
#             "-framerate",
#             "30",
#             "-i",
#             str(frame),
#             "-i",
#             str(audio_path),
#             "-t",
#             f"{duration:.3f}",
#             "-vf",
#             "scale=1920:-2,format=yuv420p",
#             "-c:v",
#             "libx264",
#             "-preset",
#             "veryfast",
#             "-tune",
#             "stillimage",
#             "-c:a",
#             "aac",
#             "-ar",
#             AUDIO_SAMPLE_RATE,
#             "-ac",
#             AUDIO_CHANNELS,
#             "-b:a",
#             AUDIO_BITRATE,
#             "-shortest",
#             str(output_path),
#         ]
#     )


# def concatenate_clips(clip_paths: list[Path]) -> None:
#     command = ["ffmpeg", "-y"]
#     for path in clip_paths:
#         command.extend(["-i", str(path)])

#     normalized_streams: list[str] = []
#     concat_inputs: list[str] = []

#     for index in range(len(clip_paths)):
#         normalized_streams.append(
#             f"[{index}:v:0]scale=1920:1080,setsar=1[v{index}];"
#             f"[{index}:a:0]aformat=sample_rates={AUDIO_SAMPLE_RATE}:channel_layouts=stereo[a{index}]"
#         )
#         concat_inputs.append(f"[v{index}][a{index}]")

#     filter_complex = (
#         ";".join(normalized_streams)
#         + ";"
#         + "".join(concat_inputs)
#         + f"concat=n={len(clip_paths)}:v=1:a=1[v][a]"
#     )

#     command.extend(
#         [
#             "-filter_complex",
#             filter_complex,
#             "-map",
#             "[v]",
#             "-map",
#             "[a]",
#             "-c:v",
#             "libx264",
#             "-preset",
#             "veryfast",
#             "-pix_fmt",
#             "yuv420p",
#             "-r",
#             "30",
#             "-c:a",
#             "aac",
#             "-ar",
#             AUDIO_SAMPLE_RATE,
#             "-ac",
#             AUDIO_CHANNELS,
#             "-b:a",
#             AUDIO_BITRATE,
#             "-movflags",
#             "+faststart",
#             str(OUTPUT),
#         ]
#     )

#     run(command)


# def existing_clip_paths() -> list[Path]:
#     return [CLIPS / "title.mp4", *sorted(CLIPS.glob("slide_*.mp4"))]


# def main() -> None:
#     for tool in ["pdftoppm", "ffmpeg", "ffprobe"]:
#         require_tool(tool)

#     if not PDF.exists():
#         raise SystemExit(f"Missing PDF: {PDF}")

#     if "--concat-only" in sys.argv:
#         clip_paths = existing_clip_paths()
#         if len(clip_paths) != len(NARRATION) + 1 or any(not path.exists() for path in clip_paths):
#             raise SystemExit("Missing generated clips; run the full generator first.")
#         concatenate_clips(clip_paths)
#         print(f"Generated {OUTPUT}")
#         return

#     if BUILD.exists():
#         shutil.rmtree(BUILD)

#     FRAMES.mkdir(parents=True)
#     AUDIO.mkdir(parents=True)
#     CLIPS.mkdir(parents=True)

#     run(["pdftoppm", "-png", "-r", "180", str(PDF), str(FRAMES / "slide")])

#     frame_paths = sorted(FRAMES.glob("slide-*.png"))

#     if len(frame_paths) != len(NARRATION):
#         raise SystemExit(
#             f"Expected {len(NARRATION)} slide images, got {len(frame_paths)}"
#         )

#     clip_paths: list[Path] = []

#     create_title_card()

#     raw_title_audio = AUDIO / "title_raw.mp3"
#     title_audio = AUDIO / "title.wav"
#     title_clip = CLIPS / "title.mp4"

#     print(f"Synthesizing title card with {VOICE}")
#     asyncio.run(synthesize_speech(TITLE_NARRATION, raw_title_audio))

#     compress_silences(raw_title_audio, title_audio)

#     title_duration = audio_duration(title_audio) + TITLE_DURATION_PAD
#     create_clip(TITLE_CARD, title_audio, title_duration, title_clip)

#     clip_paths.append(title_clip)

#     for index, (frame, narration) in enumerate(zip(frame_paths, NARRATION), start=1):
#         raw_audio_path = AUDIO / f"slide_{index:02d}_raw.mp3"
#         audio_path = AUDIO / f"slide_{index:02d}.wav"
#         clip_path = CLIPS / f"slide_{index:02d}.mp4"

#         print(f"Synthesizing slide {index:02d} with {VOICE}")

#         asyncio.run(synthesize_speech(narration, raw_audio_path))

#         compress_silences(raw_audio_path, audio_path)

#         duration = audio_duration(audio_path) + SLIDE_DURATION_PAD

#         create_clip(frame, audio_path, duration, clip_path)

#         clip_paths.append(clip_path)

#     concatenate_clips(clip_paths)

#     print(f"Generated {OUTPUT}")


# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
"""Generate a high-quality Full HD narrated MP4 video from a Beamer PDF.

The script uses:
- pdftoppm to render Beamer slides as PNG images;
- edge-tts to generate narration audio;
- ffmpeg/ffprobe to normalize audio, create video clips, and concatenate them.

Output:
- 1920x1080 Full HD MP4
- H.264 video, yuv420p pixel format for compatibility
- AAC audio
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent

PDF = ROOT / "hal_acentauri_hceres_poc_presentation.pdf"
BUILD = ROOT / "video_build"
FRAMES = BUILD / "frames"
AUDIO = BUILD / "audio"
CLIPS = BUILD / "clips"

TITLE_CARD = BUILD / "title_card.png"
OUTPUT = ROOT / "hal_acentauri_hceres_poc_presentation_narrated.mp4"


# -----------------------------------------------------------------------------
# Video quality parameters
# -----------------------------------------------------------------------------

# Full HD export.
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080

# 30 fps is enough for still-slide videos and keeps file size reasonable.
VIDEO_FPS = "30"

# Higher PDF rasterization DPI gives sharper text before downscaling to 1080p.
# Good values:
# - 180: acceptable
# - 220: good
# - 240: sharper
# - 300: very sharp but slower and heavier
RENDER_DPI = "240"

# H.264 quality. Lower CRF = better quality and larger file.
# 18 is visually high quality. 16 is excellent but heavier.
VIDEO_CRF = "18"

# Encoding preset. Slower = better compression for same quality.
# Use "medium" or "slow" for final export, "veryfast" for quick testing.
VIDEO_PRESET = "slow"

# Maximum bitrate is optional but helps prevent huge files on some encoders.
# You can set VIDEO_MAXRATE = None to disable.
VIDEO_MAXRATE = "12M"
VIDEO_BUFSIZE = "24M"


# -----------------------------------------------------------------------------
# Voice and audio parameters
# -----------------------------------------------------------------------------

VOICE = "en-US-GuyNeural"

# Slower narration.
# Try "-15%" if "-20%" feels too slow.
# Try "-25%" if it still feels too fast.
VOICE_RATE = "-20%"

AUDIO_SAMPLE_RATE = "48000"
AUDIO_CHANNELS = "2"
AUDIO_BITRATE = "192k"

TITLE_TEXT = "HAL ACENTAURI HCERES POC"
TITLE_SUBTEXT = "Narrated presentation"
TITLE_NARRATION = "HAL ACENTAURI HCERES proof of concept. Narrated presentation."

# Extra breathing time after the title card.
TITLE_DURATION_PAD = 1.0

# Extra breathing time after each slide narration.
SLIDE_DURATION_PAD = 0.8

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# -----------------------------------------------------------------------------
# Narration
# -----------------------------------------------------------------------------

NARRATION = [
    """
    This presentation introduces a reproducible bibliometric analysis pipeline
    designed to support HCERES-style evaluation preparation for the ACENTAURI
    team. The main idea is not to automate the evaluation itself, but to generate
    a verifiable working basis for expert validation. The presentation covers the
    problem, the proposed solution, the use of AI agents, the implementation
    pipeline, the generated artifacts, the first results, the demonstration path,
    the narrated video generation process, the limitations, and a final
    self-assessment.
    """,

    """
    The problem addressed is an evaluation preparation bottleneck. Preparing an
    HCERES-style evaluation requires a reliable synthesis of publications,
    collaborations, venues, open-science indicators, and validation gaps. Most of
    the source data exists in HAL, but the metadata is heterogeneous and
    sometimes incomplete. Manual extraction is slow, repetitive, difficult to
    audit, and prone to inconsistencies. The goal is therefore to accelerate and
    structure expert validation, not to replace it.
    """,

    """
    The proposed solution is a local, deterministic, and rerunnable pipeline. The
    inputs are HAL metadata and optional CSV files, such as member lists, theme
    mappings, Scimago data, or CORE conference rankings. The central component is
    a monolithic Python proof of concept called hal_acentauri_hceres_poc.py. The
    outputs are tables, figures, collaboration network exports, and report files.
    Optional CSV files enrich or correct the analysis, but they are not required
    for the pipeline to run.
    """,

    """
    AI agents were used as development accelerators. The workflow started from a
    human need: preparing a reliable HCERES-oriented analysis. ChatGPT helped
    clarify the need, structure the ideas, and draft explanatory material. Codex
    helped generate and modify the code, debug the repository, add tests,
    improve documentation, and prepare the slides and video scripts. The
    important point is that AI remains inside a validation loop. The institutional
    interpretation and final quality control remain human responsibilities.
    """,

    """
    The initial prompt asked for a simple, monolithic Python proof of concept to
    automate a HAL-based bibliometric analysis of the ACENTAURI team in a format
    useful for HCERES-style preparation. The expected behavior included querying
    HAL, cleaning metadata, filtering non-target records, deduplicating
    publications, computing indicators, accepting optional CSV enrichments, and
    generating deterministic reports with explicit provenance and no invented
    content.
    """,

    """
    The implementation pipeline follows six main steps. First, it discovers the
    HAL query or uses an explicit structure identifier. Second, it retrieves HAL
    records through paginated API calls. Third, it normalizes metadata such as
    titles, authors, dates, document types, affiliations, DOI information, and
    files. Fourth, it filters and deduplicates the records. Fifth, it computes
    indicators. Sixth, it exports the generated artifacts. The useful part is not
    only the final report, but the auditable path from HAL metadata to each
    indicator.
    """,

    """
    The pipeline explicitly distinguishes different levels of provenance and
    trust. Some information comes from verified HAL metadata. Some information is
    inferred, for example when identifying recurrent authors. Some information
    can be manually supplied through CSV files, such as validated members or
    theme mappings. Some information remains missing or unavailable. The report
    exposes these categories instead of hiding uncertainty, which is essential
    for institutional use.
    """,

    """
    The generated artifacts include repository deliverables and output files. On
    the repository side, there is a single Python module, command-line options
    for the period, team, output directory, and optional CSV files, static smoke
    tests, documentation, and example CSV files. On the output side, the pipeline
    generates CSV tables, LaTeX tables, figures, collaboration network exports, a
    Markdown summary report, and a standalone LaTeX report. The pipeline can be
    rerun locally.
    """,

    """
    The deterministic report is not free-form text invented by a language model.
    It is assembled from computed indicators, explicit metadata provenance, and
    known validation gaps. It includes the analysis scope, the team name, the
    period, the HAL query, the number of raw HAL records, and the number of
    retained publications. It also includes audit-oriented sections such as top
    authors, venues, collaboration patterns, open-science indicators, missing
    optional data, limitations, and validation needs.
    """,

    """
    In the existing run, the pipeline retrieved sixty-nine HAL records. After
    filtering, it retained fifty-eight publications and identified or inferred
    thirty-one members. It generated Markdown, LaTeX, and PDF reports. The
    open-science indicators showed fifty-six publications with full text in HAL,
    two without full text, twenty-four publications with DOI, fifty-five English
    publications, and three French publications. These numbers provide a first
    audit basis, not a final institutional validation.
    """,

    """
    The demonstration path is straightforward. First, run the pipeline with
    python hal_acentauri_hceres_poc.py and select the output directory. Then
    inspect the generated Markdown report in outputs slash reports slash
    hceres_summary_report dot md. Next, open the generated LaTeX tables and
    figures. Finally, explain where optional enrichment files enter the workflow,
    such as acentauri_members, theme_mapping, scimago_journals, and
    core_conferences.
    """,

    """
    The narrated video is synchronized at the level of each slide. Each slide has
    a dedicated narration paragraph. The script uses the generated audio duration
    to keep each slide on screen for the right amount of time. The text-to-speech
    voice is slowed down to improve comprehension. Long silences are compressed
    to avoid empty waiting time, and a title card is inserted before the slide
    sequence. Codex helped create the script, adjust the voice speed, compress
    silences, and regenerate the final MP4.
    """,

    """
    The video generation process starts from the Beamer source and the narration
    script. The Beamer source is compiled to PDF with pdflatex. Each PDF page is
    rendered as a PNG image with pdftoppm. Then edge-tts generates one audio
    narration file per slide. FFmpeg is used to process the audio, compress long
    silences, create one still-image video clip per slide, match each clip
    duration to its narration, and concatenate all clips into the final MP4. The
    result is a narrated video with synchronized slides and more natural pacing.
    """,

    """
    The main limitations are incomplete or heterogeneous HAL metadata, partly
    inferred member identification when no validated CSV is provided, missing
    ARC, RIC, and MOC theme mapping, and heuristic partner classification. The
    next steps are to validate the member list, provide theme mapping, add
    Scimago and CORE reference data, and add domain-level quality control before
    institutional use. The key conclusion is that AI accelerates implementation,
    deterministic processing makes outputs reproducible, and human validation
    gives the result institutional value.
    """,

    """
    The final slide gives a self-assessment of the AI-assisted workflow. ChatGPT
    and Codex supported idea structuring, implementation, debugging, tests,
    documentation, report generation, slide drafting, and video generation.
    Without AI, this work was estimated to take more than one week, or more than
    forty hours. With AI, the estimated time was about three hours. The estimated
    time saved was therefore more than thirty-seven hours, or several working
    days. The final message is that AI can accelerate practical research
    administration tooling, but the generated outputs must remain deterministic,
    auditable, and validated by humans.
    """,
]


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing required tool: {name}")


def ffmpeg_video_quality_args() -> list[str]:
    """Return H.264 quality parameters used for every encode."""
    args = [
        "-c:v",
        "libx264",
        "-preset",
        VIDEO_PRESET,
        "-crf",
        VIDEO_CRF,
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
    ]

    if VIDEO_MAXRATE and VIDEO_BUFSIZE:
        args.extend(["-maxrate", VIDEO_MAXRATE, "-bufsize", VIDEO_BUFSIZE])

    return args


def full_hd_filter() -> str:
    """Scale/pad any input to exact 1920x1080 without distortion."""
    return (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,format=yuv420p"
    )


async def synthesize_speech(text: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(
        normalize_narration(text),
        VOICE,
        rate=VOICE_RATE,
    )
    await communicate.save(str(output_path))


def normalize_narration(text: str) -> str:
    """Avoid unintended TTS pauses from line wrapping and technical notation."""
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "HCERES-style": "HCERES style",
        "HAL-based": "HAL based",
        "audit-oriented": "audit oriented",
        "end-to-end": "end to end",
        "edge TTS": "Edge text to speech",
        "edge-tts": "Edge text to speech",
        "ffmpeg": "F Fmpeg",
        "ffprobe": "F Fprobe",
        "pdflatex": "P D F LaTeX",
        "pdftoppm": "P D F to P P M",
        "Scimago": "SCImago",
        "ACENTAURI": "Acentauri",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return float(result.stdout.strip())


def normalize_audio(source_path: Path, output_path: Path) -> None:
    """Normalize audio format without aggressively removing silences.

    This avoids choppy or unnatural narration. If you later want silence removal,
    add a silenceremove filter before aresample.
    """
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-af",
            f"aresample={AUDIO_SAMPLE_RATE}:async=1000:first_pts=0",
            "-ar",
            AUDIO_SAMPLE_RATE,
            "-ac",
            AUDIO_CHANNELS,
            str(output_path),
        ]
    )


# Backward-compatible alias.
compress_silences = normalize_audio


# -----------------------------------------------------------------------------
# Video generation
# -----------------------------------------------------------------------------

def create_title_card() -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x164194:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1",
            "-vf",
            (
                f"drawtext=fontfile={FONT_BOLD}:text='{TITLE_TEXT}':"
                "fontcolor=white:fontsize=70:x=(w-text_w)/2:y=390,"
                f"drawtext=fontfile={FONT_REGULAR}:text='{TITLE_SUBTEXT}':"
                "fontcolor=white:fontsize=34:x=(w-text_w)/2:y=500,"
                "format=yuv420p"
            ),
            "-frames:v",
            "1",
            str(TITLE_CARD),
        ]
    )


def create_clip(frame: Path, audio_path: Path, duration: float, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        VIDEO_FPS,
        "-i",
        str(frame),
        "-i",
        str(audio_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        full_hd_filter(),
        *ffmpeg_video_quality_args(),
        "-r",
        VIDEO_FPS,
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-ar",
        AUDIO_SAMPLE_RATE,
        "-ac",
        AUDIO_CHANNELS,
        "-b:a",
        AUDIO_BITRATE,
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    run(command)


def concatenate_clips(clip_paths: list[Path]) -> None:
    command = ["ffmpeg", "-y"]

    for path in clip_paths:
        command.extend(["-i", str(path)])

    normalized_streams: list[str] = []
    concat_inputs: list[str] = []

    for index in range(len(clip_paths)):
        normalized_streams.append(
            f"[{index}:v:0]"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,format=yuv420p[v{index}];"
            f"[{index}:a:0]"
            f"aformat=sample_rates={AUDIO_SAMPLE_RATE}:channel_layouts=stereo[a{index}]"
        )
        concat_inputs.append(f"[v{index}][a{index}]")

    filter_complex = (
        ";".join(normalized_streams)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={len(clip_paths)}:v=1:a=1[v][a]"
    )

    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            *ffmpeg_video_quality_args(),
            "-r",
            VIDEO_FPS,
            "-c:a",
            "aac",
            "-ar",
            AUDIO_SAMPLE_RATE,
            "-ac",
            AUDIO_CHANNELS,
            "-b:a",
            AUDIO_BITRATE,
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ]
    )

    run(command)


def existing_clip_paths() -> list[Path]:
    return [CLIPS / "title.mp4", *sorted(CLIPS.glob("slide_*.mp4"))]


def check_output_quality(path: Path) -> None:
    if not path.exists():
        return

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,pix_fmt,codec_name",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    print("\nVideo stream:")
    print(result.stdout.strip())


def main() -> None:
    for tool in ["pdftoppm", "ffmpeg", "ffprobe"]:
        require_tool(tool)

    if not PDF.exists():
        raise SystemExit(f"Missing PDF: {PDF}")

    if "--concat-only" in sys.argv:
        clip_paths = existing_clip_paths()
        if len(clip_paths) != len(NARRATION) + 1 or any(not path.exists() for path in clip_paths):
            raise SystemExit("Missing generated clips; run the full generator first.")
        concatenate_clips(clip_paths)
        print(f"Generated {OUTPUT}")
        check_output_quality(OUTPUT)
        return

    if BUILD.exists():
        shutil.rmtree(BUILD)

    FRAMES.mkdir(parents=True)
    AUDIO.mkdir(parents=True)
    CLIPS.mkdir(parents=True)

    # Render slides as high-resolution PNGs first, then downscale cleanly to Full HD.
    run(["pdftoppm", "-png", "-r", RENDER_DPI, str(PDF), str(FRAMES / "slide")])

    frame_paths = sorted(FRAMES.glob("slide-*.png"))

    if len(frame_paths) != len(NARRATION):
        raise SystemExit(
            f"Expected {len(NARRATION)} slide images, got {len(frame_paths)}"
        )

    clip_paths: list[Path] = []

    create_title_card()

    raw_title_audio = AUDIO / "title_raw.mp3"
    title_audio = AUDIO / "title.wav"
    title_clip = CLIPS / "title.mp4"

    print(f"Synthesizing title card with {VOICE}")
    asyncio.run(synthesize_speech(TITLE_NARRATION, raw_title_audio))

    normalize_audio(raw_title_audio, title_audio)

    title_duration = audio_duration(title_audio) + TITLE_DURATION_PAD
    create_clip(TITLE_CARD, title_audio, title_duration, title_clip)

    clip_paths.append(title_clip)

    for index, (frame, narration) in enumerate(zip(frame_paths, NARRATION), start=1):
        raw_audio_path = AUDIO / f"slide_{index:02d}_raw.mp3"
        audio_path = AUDIO / f"slide_{index:02d}.wav"
        clip_path = CLIPS / f"slide_{index:02d}.mp4"

        print(f"Synthesizing slide {index:02d} with {VOICE}")

        asyncio.run(synthesize_speech(narration, raw_audio_path))

        normalize_audio(raw_audio_path, audio_path)

        duration = audio_duration(audio_path) + SLIDE_DURATION_PAD

        create_clip(frame, audio_path, duration, clip_path)

        clip_paths.append(clip_path)

    concatenate_clips(clip_paths)

    print(f"Generated {OUTPUT}")
    check_output_quality(OUTPUT)


if __name__ == "__main__":
    main()