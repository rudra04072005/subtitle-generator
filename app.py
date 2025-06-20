import streamlit as st
import whisper
from deep_translator import GoogleTranslator
from datetime import timedelta
import os
import tempfile
import srt
import subprocess

# --------------------------
# USER LOGIN CONFIGURATION
# --------------------------
USERS = {
    "admin": "admin123",
    "user1": "pass1",
    "user2": "pass2"
}

def login():
    st.title("🔐 Login Required")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if USERS.get(username) == password:
                st.session_state["logged_in"] = True
                st.session_state["user"] = username
                st.success(f"Welcome, {username}!")
                st.rerun()  
            else:
                st.error("Invalid username or password")

# --------------------------
# SUBTITLE PROCESSING
# --------------------------

# Create output folder
os.makedirs("outputs", exist_ok=True)

# Language name to code


LANG_DICT = {
    name.title(): code
    for name, code in GoogleTranslator().get_supported_languages(as_dict=True).items()
}

def format_timestamp(seconds):
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    millis = int((seconds - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

def generate_srt(segments, tgt_lang, progress_callback):
    translator = GoogleTranslator(source="auto", target=tgt_lang)
    total = len(segments)
    subs = []

    for i, seg in enumerate(segments, start=1):
        start = timedelta(seconds=seg["start"])
        end = timedelta(seconds=seg["end"])
        try:
            translated = translator.translate(seg["text"])
        except:
            translated = "[Translation Error]"
        subs.append(srt.Subtitle(index=i, start=start, end=end, content=translated))
        progress_callback(0.3 + 0.6 * (i / total))

    return srt.compose(subs)

def burn_subtitles(input_video_path, srt_path, output_video_path):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_video_path,
        "-vf", f"subtitles={srt_path}",
        "-c:a", "copy",
        output_video_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr}")

# --------------------------
# MAIN APP
# --------------------------
def main():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login()
        return

    st.sidebar.success(f"Logged in as: {st.session_state['user']}")
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.experimental_rerun()

    st.title("🎥 Whisper Subtitle Translator")

    uploaded_file = st.file_uploader("Upload video or audio file", type=["mp4", "wav", "mp3"])

    source_lang_name = st.selectbox("Spoken Language", list(LANG_DICT.keys()), index=list(LANG_DICT.keys()).index("English"))
    target_lang_name = st.selectbox("Subtitle Language", list(LANG_DICT.keys()), index=list(LANG_DICT.keys()).index("Hindi"))

    source_lang_code = LANG_DICT[source_lang_name]
    target_lang_code = LANG_DICT[target_lang_name]

    if uploaded_file and st.button("Generate Subtitles"):
        with st.spinner("Processing..."):
            temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            temp_input.write(uploaded_file.read())
            temp_input.close()

            st.info("Loading Whisper model...")
            model = whisper.load_model("base")
            st.success("Model loaded. Transcribing...")

            result = model.transcribe(temp_input.name, language=source_lang_code)
            segments = result["segments"]
            full_text = result["text"]

            progress_bar = st.progress(0.0)
            progress_bar.progress(0.3)

            st.info("Translating and generating subtitles...")
            srt_content = generate_srt(segments, target_lang_code, progress_bar.progress)

            base_name = os.path.basename(temp_input.name).split('.')[0]
            srt_filename = f"{base_name}.srt"
            txt_filename = f"{base_name}_transcript.txt"
            burned_video_name = f"{base_name}_with_subs.mp4"

            srt_path = os.path.join("outputs", srt_filename)
            txt_path = os.path.join("outputs", txt_filename)
            burned_video_path = os.path.join("outputs", burned_video_name)

            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            burn_subtitles(temp_input.name, srt_path, burned_video_path)

            with open(srt_path, "r", encoding="utf-8") as f:
                st.session_state["srt_data"] = f.read()

            with open(txt_path, "r", encoding="utf-8") as f:
                st.session_state["txt_data"] = f.read()

            with open(burned_video_path, "rb") as f:
                st.session_state["video_data"] = f.read()

            st.session_state["srt_name"] = srt_filename
            st.session_state["txt_name"] = txt_filename
            st.session_state["video_name"] = burned_video_name

            progress_bar.progress(1.0)
            st.success("Subtitle, transcript, and video are ready!")

    if st.session_state.get("srt_data"):
        st.download_button("📥 Download Subtitle (.srt)", data=st.session_state["srt_data"], file_name=st.session_state["srt_name"])

    if st.session_state.get("txt_data"):
        st.download_button("📘 Download Transcript (.txt)", data=st.session_state["txt_data"], file_name=st.session_state["txt_name"])

    if st.session_state.get("video_data"):
        st.download_button("🎬 Download Video with Burned Subtitles", data=st.session_state["video_data"], file_name=st.session_state["video_name"])

# --------------------------
# RUN THE APP
# --------------------------
if __name__ == "__main__":
    main()
