"""
OCTI Meeting Launcher - Windows Orchestrator
Automatically detects meetings and manages transcription scripts.
Small circular bubble UI with octopus logo.
"""

import subprocess
import psutil
import time
import os
import sys
import signal
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk  # pip install pillow

# Configuration
MEETING_APPS = {
    "Zoom": ["Zoom.exe", "CptHost.exe"],
    "Teams": ["ms-teams.exe", "Teams.exe"],
    "Google Meet": ["chrome.exe", "msedge.exe", "firefox.exe"],
}

SCRIPT_PATHS = {
    "mic": "octiMic.py",
    "speaker": "octiSpeaker.py",
    "combined": "octiCombined.py"
}

LOGO_FILE = "octopus_logo.png"

# Bubble config
BUBBLE_SIZE = 70        # small bubble
BORDER_WIDTH = 6        # thick outer ring

# Global state
recording_processes = {}
is_recording = False
root = None
status_label = None   # kept for compatibility with your logic
button = None         # kept for compatibility with your logic

# bubble drawing state
canvas = None
border_circle_id = None
logo_img = None
drag_offset_x = 0
drag_offset_y = 0


def check_meeting_running():
    """Check if any meeting app is running."""
    running_processes = {p.name().lower(): p for p in psutil.process_iter(['name'])}
    
    for app_name, process_names in MEETING_APPS.items():
        for proc_name in process_names:
            if proc_name.lower() in running_processes:
                # keep your original behavior: skip raw browser
                if proc_name.lower() in ["chrome.exe", "msedge.exe", "firefox.exe"]:
                    continue
                return app_name
    
    return None


# --------- Bubble helpers (pure UI) --------- #

def set_border_color(color: str):
    """Change the outer ring color of the bubble."""
    global canvas, border_circle_id
    if canvas is not None and border_circle_id is not None:
        canvas.itemconfig(border_circle_id, outline=color)


def show_bubble():
    if root:
        root.deiconify()
        root.attributes("-alpha", 0.98)


def hide_bubble():
    if root:
        root.withdraw()


def on_bubble_press(event):
    """For dragging."""
    global drag_offset_x, drag_offset_y
    drag_offset_x = event.x
    drag_offset_y = event.y


def on_bubble_drag(event):
    """Drag bubble around screen."""
    x = event.x_root - drag_offset_x
    y = event.y_root - drag_offset_y
    root.geometry(f"{BUBBLE_SIZE}x{BUBBLE_SIZE}+{x}+{y}")


def on_bubble_click(event):
    """Left-click: toggle start/stop using your existing functions."""
    global is_recording
    if not is_recording:
        start_recording()
    else:
        stop_recording()


# --------- ORIGINAL LOGIC (UNCHANGED except border color calls) --------- #

def start_recording():
    """Start all recording scripts."""
    global recording_processes, is_recording
    
    if is_recording:
        return
    
    # Verify scripts exist
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    for script_type, script_path in SCRIPT_PATHS.items():
        full_path = os.path.join(script_dir, script_path)
        if not os.path.exists(full_path):
            messagebox.showerror("Error", f"Script not found: {full_path}")
            return
    
    is_recording = True
    recording_processes = {}
    
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Start mic script
        mic_path = os.path.join(script_dir, SCRIPT_PATHS["mic"])
        print(f"Starting mic: {mic_path}")
        mic_proc = subprocess.Popen(
            [sys.executable, mic_path],
            stdout=subprocess.DEVNULL,  # Don't capture - let it run freely
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=script_dir
        )
        recording_processes["mic"] = mic_proc
        
        # Start speaker script
        speaker_path = os.path.join(script_dir, SCRIPT_PATHS["speaker"])
        print(f"Starting speaker: {speaker_path}")
        speaker_proc = subprocess.Popen(
            [sys.executable, speaker_path],
            stdout=subprocess.DEVNULL,  # Don't capture - let it run freely
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=script_dir
        )
        recording_processes["speaker"] = speaker_proc
        
        # Wait a moment to check if they started
        time.sleep(2)
        
        # Check if processes are still running
        if mic_proc.poll() is not None:
            print(f"Mic script exited immediately with code {mic_proc.returncode}")
            messagebox.showerror("Error", f"Mic script failed to start (exit code {mic_proc.returncode})")
            if speaker_proc.poll() is None:
                speaker_proc.terminate()
            is_recording = False
            recording_processes = {}
            set_border_color("gray")
            return
        
        if speaker_proc.poll() is not None:
            print(f"Speaker script exited immediately with code {speaker_proc.returncode}")
            messagebox.showerror("Error", f"Speaker script failed to start (exit code {speaker_proc.returncode})")
            if mic_proc.poll() is None:
                mic_proc.terminate()
            is_recording = False
            recording_processes = {}
            set_border_color("gray")
            return
        
        update_status("🟢 Recording...", "green")
        set_border_color("#00C851")  # bright green ring
        # button is invisible, but keep behaviour so logic untouched
        if button:
            button.config(text="⏹ Stop Recording", command=stop_recording)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start: {e}")
        is_recording = False
        recording_processes = {}
        set_border_color("gray")


def stop_recording():
    """Stop all recording scripts and process."""
    global recording_processes, is_recording
    
    if not is_recording:
        return
    
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    
    update_status("⏸ Stopping...", "orange")
    set_border_color("#ff4444")  # red while stopping/processing
    if button:
        button.config(state="disabled")
    if root:
        root.update()
    
    # Stop processes - send SIGINT (KeyboardInterrupt) so they can save files
    for name, proc in recording_processes.items():
        if proc and proc.poll() is None:
            try:
                if sys.platform == "win32":
                    # On Windows, try to send CTRL_C_EVENT (KeyboardInterrupt)
                    try:
                        proc.send_signal(signal.CTRL_C_EVENT)
                    except:
                        # If that fails, use terminate
                        proc.terminate()
                else:
                    # On Unix, send SIGINT (KeyboardInterrupt)
                    proc.send_signal(signal.SIGINT)
            except Exception as e:
                print(f"Error sending signal to {name}: {e}")
                # Fallback to terminate
                try:
                    proc.terminate()
                except:
                    pass
    
    # Wait for processes to finish (give them time to process and save)
    print("Waiting for processes to finish...")
    for name, proc in list(recording_processes.items()):
        if proc:
            try:
                # Give them time to catch KeyboardInterrupt and process
                proc.wait(timeout=180)  # 3 minutes max
                print(f"{name} finished with code {proc.returncode}")
            except subprocess.TimeoutExpired:
                print(f"{name} timed out, killing...")
                proc.kill()
                proc.wait()
            except Exception as e:
                print(f"Error waiting for {name}: {e}")
    
    recording_processes = {}
    is_recording = False
    
    # Wait for files to be created
    update_status("⏳ Processing...", "blue")
    if root:
        root.update()
    
    mic_file = os.path.join(script_dir, "Mic_transcript.txt")
    spk_file = os.path.join(script_dir, "Speaker_transcript.txt")
    
    # Wait up to 120 seconds for files (transcription can take time)
    print("Waiting for transcript files...")
    for i in range(60):  # 60 * 2 = 120 seconds
        time.sleep(2)
        mic_exists = os.path.exists(mic_file)
        spk_exists = os.path.exists(spk_file)
        if mic_exists and spk_exists:
            print("Both transcript files found!")
            break
        if i % 5 == 0:  # Print status every 10 seconds
            print(f"Waiting... Mic: {mic_exists}, Speaker: {spk_exists}")
        if root:
            root.update()
    
    # Check if files exist
    if not os.path.exists(mic_file) or not os.path.exists(spk_file):
        missing = []
        if not os.path.exists(mic_file):
            missing.append("Mic_transcript.txt")
        if not os.path.exists(spk_file):
            missing.append("Speaker_transcript.txt")
        messagebox.showerror(
            "Error",
            f"Missing files:\n" + "\n".join(missing) + "\n\nCheck if recording captured audio."
        )
        update_status("❌ Failed", "red")
        set_border_color("gray")
        if button:
            button.config(text="▶ Start Recording", command=start_recording, state="normal")
        return
    
    # Run combined script
    update_status("🔄 Merging...", "blue")
    if root:
        root.update()
    
    try:
        combined_path = os.path.join(script_dir, SCRIPT_PATHS["combined"])
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        combined_proc = subprocess.Popen(
            [sys.executable, combined_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            cwd=script_dir
        )
        
        stdout, stderr = combined_proc.communicate(timeout=300)
        
        if combined_proc.returncode != 0:
            print(f"Combined script error: {stderr[:500]}")
    except Exception as e:
        print(f"Error running combined script: {e}")
    
    # Check results
    summary_file = os.path.join(script_dir, "Meeting_summary.txt")
    combined_file = os.path.join(script_dir, "Combined_transcript.txt")
    
    if os.path.exists(summary_file) and os.path.exists(combined_file):
        update_status("✅ Complete!", "green")
        messagebox.showinfo(
            "Complete",
            "Files created:\n- Combined_transcript.txt\n- Meeting_summary.txt"
        )
    else:
        update_status("⚠️ Partial", "orange")
        messagebox.showwarning(
            "Warning",
            f"Combined: {'✓' if os.path.exists(combined_file) else '✗'}\n"
            f"Summary: {'✓' if os.path.exists(summary_file) else '✗'}"
        )
    
    if button:
        button.config(text="▶ Start Recording", command=start_recording, state="normal")

    # after everything, hide bubble
    if root:
        root.after(1000, hide_bubble)


def update_status(text, color="black"):
    """Update status label (still exists but not shown visually)."""
    if status_label:
        status_label.config(text=text, fg=color)
    # Also print to console for debugging
    print(text)


def monitor_meetings():
    """Background thread to monitor for meeting apps."""
    meeting_detected = False
    
    while True:
        meeting_app = check_meeting_running()
        
        if meeting_app and not meeting_detected:
            meeting_detected = True
            if root:
                root.after(0, lambda: update_status(f"📹 {meeting_app} detected", "blue"))
                root.after(0, show_bubble)
        
        elif not meeting_app and meeting_detected:
            meeting_detected = False
            if root and not is_recording:
                root.after(0, lambda: update_status("⏸ No meeting", "gray"))
                root.after(0, hide_bubble)
        
        time.sleep(2)


def create_gui():
    """Create the small circular bubble window."""
    global root, status_label, button, canvas, border_circle_id, logo_img
    
    root = tk.Tk()
    root.title("OCTI Meeting Recorder")
    
    # Small borderless always-on-top window
    root.geometry(f"{BUBBLE_SIZE}x{BUBBLE_SIZE}")
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    # Make window background transparent except bubble
    TRANSPARENT_COLOR = "#ff00ff"
    root.config(bg=TRANSPARENT_COLOR)
    root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
    
    # Position near top-right
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    x = screen_w - BUBBLE_SIZE - 40
    y = 80
    root.geometry(f"{BUBBLE_SIZE}x{BUBBLE_SIZE}+{x}+{y}")
    
    # Canvas for bubble
    canvas = tk.Canvas(
        root,
        width=BUBBLE_SIZE,
        height=BUBBLE_SIZE,
        highlightthickness=0,
        bg=TRANSPARENT_COLOR
    )
    canvas.pack(fill="both", expand=True)
    
    # Draw white circle with colored border (initially gray)
    padding = 4
    border_circle_id = canvas.create_oval(
        padding,
        padding,
        BUBBLE_SIZE - padding,
        BUBBLE_SIZE - padding,
        outline="gray",
        width=BORDER_WIDTH,
        fill="white"
    )
    
    # Load and scale logo
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    logo_path = os.path.join(script_dir, LOGO_FILE)
    try:
        img = Image.open(logo_path).convert("RGBA")
        # scale to fit inside circle (60% of bubble)
        target = int(BUBBLE_SIZE * 0.55)
        img.thumbnail((target, target), Image.LANCZOS)
        logo_img = ImageTk.PhotoImage(img)
        canvas.create_image(
            BUBBLE_SIZE // 2,
            BUBBLE_SIZE // 2,
            image=logo_img
        )
    except Exception as e:
        print("Logo load error:", e)
    
    # Invisible label & button (for compatibility with your existing logic)
    status_label = tk.Label(root)
    button = tk.Button(root)
    # not packing them => they never show
    
    # Mouse bindings
    canvas.bind("<ButtonPress-1>", on_bubble_press)
    canvas.bind("<B1-Motion>", on_bubble_drag)
    canvas.bind("<ButtonRelease-1>", on_bubble_click)
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_meetings, daemon=True)
    monitor_thread.start()
    
    # Start hidden until meeting is detected
    hide_bubble()
    root.mainloop()


if __name__ == "__main__":
    try:
        import psutil  # ensure installed
    except ImportError:
        print("Error: psutil not installed. Install it with: pip install psutil")
        sys.exit(1)
    
    script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    missing = [path for path in SCRIPT_PATHS.values() 
               if not os.path.exists(os.path.join(script_dir, path))]
    if missing:
        print(f"Error: Missing scripts: {', '.join(missing)}")
        sys.exit(1)
    
    print("Starting OCTI Meeting Launcher...")
    create_gui()


#_______________________________________________________Older Version______________________________________________________________________________________________
# #!/usr/bin/env python3
# """
# OCTI Meeting Launcher - Windows Orchestrator
# Automatically detects meetings and manages transcription scripts.
# """

# import subprocess
# import psutil
# import time
# import os
# import sys
# import signal
# import threading
# import tkinter as tk
# from tkinter import ttk, messagebox

# # Configuration
# MEETING_APPS = {
#     "Zoom": ["Zoom.exe", "CptHost.exe"],
#     "Teams": ["ms-teams.exe", "Teams.exe"],
#     "Google Meet": ["chrome.exe", "msedge.exe", "firefox.exe"],
# }

# SCRIPT_PATHS = {
#     "mic": "octiMic.py",
#     "speaker": "octiSpeaker.py",
#     "combined": "octiCombined.py"
# }

# # Global state
# recording_processes = {}
# is_recording = False
# root = None
# status_label = None
# button = None


# def check_meeting_running():
#     """Check if any meeting app is running."""
#     running_processes = {p.name().lower(): p for p in psutil.process_iter(['name'])}
    
#     for app_name, process_names in MEETING_APPS.items():
#         for proc_name in process_names:
#             if proc_name.lower() in running_processes:
#                 if proc_name.lower() in ["chrome.exe", "msedge.exe", "firefox.exe"]:
#                     continue
#                 return app_name
    
#     return None


# def start_recording():
#     """Start all recording scripts."""
#     global recording_processes, is_recording
    
#     if is_recording:
#         return
    
#     # Verify scripts exist
#     script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
#     for script_type, script_path in SCRIPT_PATHS.items():
#         full_path = os.path.join(script_dir, script_path)
#         if not os.path.exists(full_path):
#             messagebox.showerror("Error", f"Script not found: {full_path}")
#             return
    
#     is_recording = True
#     recording_processes = {}
    
#     try:
#         env = os.environ.copy()
#         env['PYTHONIOENCODING'] = 'utf-8'
        
#         # Start mic script
#         mic_path = os.path.join(script_dir, SCRIPT_PATHS["mic"])
#         print(f"Starting mic: {mic_path}")
#         mic_proc = subprocess.Popen(
#             [sys.executable, mic_path],
#             stdout=subprocess.DEVNULL,  # Don't capture - let it run freely
#             stderr=subprocess.DEVNULL,
#             env=env,
#             cwd=script_dir
#         )
#         recording_processes["mic"] = mic_proc
        
#         # Start speaker script
#         speaker_path = os.path.join(script_dir, SCRIPT_PATHS["speaker"])
#         print(f"Starting speaker: {speaker_path}")
#         speaker_proc = subprocess.Popen(
#             [sys.executable, speaker_path],
#             stdout=subprocess.DEVNULL,  # Don't capture - let it run freely
#             stderr=subprocess.DEVNULL,
#             env=env,
#             cwd=script_dir
#         )
#         recording_processes["speaker"] = speaker_proc
        
#         # Wait a moment to check if they started
#         time.sleep(2)
        
#         # Check if processes are still running
#         if mic_proc.poll() is not None:
#             print(f"Mic script exited immediately with code {mic_proc.returncode}")
#             messagebox.showerror("Error", f"Mic script failed to start (exit code {mic_proc.returncode})")
#             if speaker_proc.poll() is None:
#                 speaker_proc.terminate()
#             is_recording = False
#             recording_processes = {}
#             return
        
#         if speaker_proc.poll() is not None:
#             print(f"Speaker script exited immediately with code {speaker_proc.returncode}")
#             messagebox.showerror("Error", f"Speaker script failed to start (exit code {speaker_proc.returncode})")
#             if mic_proc.poll() is None:
#                 mic_proc.terminate()
#             is_recording = False
#             recording_processes = {}
#             return
        
#         update_status("🟢 Recording...", "green")
#         button.config(text="⏹ Stop Recording", command=stop_recording)
        
#     except Exception as e:
#         messagebox.showerror("Error", f"Failed to start: {e}")
#         is_recording = False
#         recording_processes = {}


# def stop_recording():
#     """Stop all recording scripts and process."""
#     global recording_processes, is_recording
    
#     if not is_recording:
#         return
    
#     script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    
#     update_status("⏸ Stopping...", "orange")
#     button.config(state="disabled")
#     root.update()
    
#     # Stop processes - send SIGINT (KeyboardInterrupt) so they can save files
#     for name, proc in recording_processes.items():
#         if proc and proc.poll() is None:
#             try:
#                 if sys.platform == "win32":
#                     # On Windows, try to send CTRL_C_EVENT (KeyboardInterrupt)
#                     try:
#                         proc.send_signal(signal.CTRL_C_EVENT)
#                     except:
#                         # If that fails, use terminate
#                         proc.terminate()
#                 else:
#                     # On Unix, send SIGINT (KeyboardInterrupt)
#                     proc.send_signal(signal.SIGINT)
#             except Exception as e:
#                 print(f"Error sending signal to {name}: {e}")
#                 # Fallback to terminate
#                 try:
#                     proc.terminate()
#                 except:
#                     pass
    
#     # Wait for processes to finish (give them time to process and save)
#     print("Waiting for processes to finish...")
#     for name, proc in list(recording_processes.items()):
#         if proc:
#             try:
#                 # Give them time to catch KeyboardInterrupt and process
#                 proc.wait(timeout=180)  # 3 minutes max
#                 print(f"{name} finished with code {proc.returncode}")
#             except subprocess.TimeoutExpired:
#                 print(f"{name} timed out, killing...")
#                 proc.kill()
#                 proc.wait()
#             except Exception as e:
#                 print(f"Error waiting for {name}: {e}")
    
#     recording_processes = {}
#     is_recording = False
    
#     # Wait for files to be created
#     update_status("⏳ Processing...", "blue")
#     root.update()
    
#     mic_file = os.path.join(script_dir, "Mic_transcript.txt")
#     spk_file = os.path.join(script_dir, "Speaker_transcript.txt")
    
#     # Wait up to 120 seconds for files (transcription can take time)
#     print("Waiting for transcript files...")
#     for i in range(60):  # 60 * 2 = 120 seconds
#         time.sleep(2)
#         mic_exists = os.path.exists(mic_file)
#         spk_exists = os.path.exists(spk_file)
#         if mic_exists and spk_exists:
#             print("Both transcript files found!")
#             break
#         if i % 5 == 0:  # Print status every 10 seconds
#             print(f"Waiting... Mic: {mic_exists}, Speaker: {spk_exists}")
#         root.update()
    
#     # Check if files exist
#     if not os.path.exists(mic_file) or not os.path.exists(spk_file):
#         missing = []
#         if not os.path.exists(mic_file):
#             missing.append("Mic_transcript.txt")
#         if not os.path.exists(spk_file):
#             missing.append("Speaker_transcript.txt")
#         messagebox.showerror(
#             "Error",
#             f"Missing files:\n" + "\n".join(missing) + "\n\nCheck if recording captured audio."
#         )
#         update_status("❌ Failed", "red")
#         button.config(text="▶ Start Recording", command=start_recording, state="normal")
#         return
    
#     # Run combined script
#     update_status("🔄 Merging...", "blue")
#     root.update()
    
#     try:
#         combined_path = os.path.join(script_dir, SCRIPT_PATHS["combined"])
#         env = os.environ.copy()
#         env['PYTHONIOENCODING'] = 'utf-8'
        
#         combined_proc = subprocess.Popen(
#             [sys.executable, combined_path],
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding='utf-8',
#             errors='replace',
#             env=env,
#             cwd=script_dir
#         )
        
#         stdout, stderr = combined_proc.communicate(timeout=300)
        
#         if combined_proc.returncode != 0:
#             print(f"Combined script error: {stderr[:500]}")
#     except Exception as e:
#         print(f"Error running combined script: {e}")
    
#     # Check results
#     summary_file = os.path.join(script_dir, "Meeting_summary.txt")
#     combined_file = os.path.join(script_dir, "Combined_transcript.txt")
    
#     if os.path.exists(summary_file) and os.path.exists(combined_file):
#         update_status("✅ Complete!", "green")
#         messagebox.showinfo(
#             "Complete",
#             "Files created:\n- Combined_transcript.txt\n- Meeting_summary.txt"
#         )
#     else:
#         update_status("⚠️ Partial", "orange")
#         messagebox.showwarning(
#             "Warning",
#             f"Combined: {'✓' if os.path.exists(combined_file) else '✗'}\n"
#             f"Summary: {'✓' if os.path.exists(summary_file) else '✗'}"
#         )
    
#     button.config(text="▶ Start Recording", command=start_recording, state="normal")


# def update_status(text, color="black"):
#     """Update status label."""
#     if status_label:
#         status_label.config(text=text, fg=color)


# def monitor_meetings():
#     """Background thread to monitor for meeting apps."""
#     meeting_detected = False
    
#     while True:
#         meeting_app = check_meeting_running()
        
#         if meeting_app and not meeting_detected:
#             meeting_detected = True
#             if root:
#                 root.after(0, lambda: update_status(f"📹 {meeting_app} detected", "blue"))
#                 root.after(0, lambda: button.config(state="normal"))
        
#         elif not meeting_app and meeting_detected:
#             meeting_detected = False
#             if root and not is_recording:
#                 root.after(0, lambda: update_status("⏸ No meeting", "gray"))
#                 root.after(0, lambda: button.config(state="disabled"))
        
#         time.sleep(2)


# def create_gui():
#     """Create the main GUI window."""
#     global root, status_label, button
    
#     root = tk.Tk()
#     root.title("OCTI Meeting Recorder")
#     root.geometry("400x200")
#     root.resizable(False, False)
    
#     # Center window
#     root.update_idletasks()
#     x = (root.winfo_screenwidth() // 2) - (400 // 2)
#     y = (root.winfo_screenheight() // 2) - (200 // 2)
#     root.geometry(f"400x200+{x}+{y}")
    
#     root.attributes("-topmost", True)
    
#     # Title
#     title_label = tk.Label(
#         root,
#         text="🎙 OCTI Meeting Recorder",
#         font=("Arial", 16, "bold"),
#         pady=20
#     )
#     title_label.pack()
    
#     # Status label
#     status_label = tk.Label(
#         root,
#         text="🔍 Detecting meetings...",
#         font=("Arial", 10),
#         fg="gray",
#         pady=10
#     )
#     status_label.pack()
    
#     # Button
#     button = tk.Button(
#         root,
#         text="▶ Start Recording",
#         font=("Arial", 12, "bold"),
#         bg="#4CAF50",
#         fg="white",
#         activebackground="#45a049",
#         activeforeground="white",
#         width=20,
#         height=2,
#         state="disabled",
#         command=start_recording,
#         cursor="hand2"
#     )
#     button.pack(pady=10)
    
#     # Start monitoring thread
#     monitor_thread = threading.Thread(target=monitor_meetings, daemon=True)
#     monitor_thread.start()
    
#     # Handle window close
#     def on_closing():
#         if is_recording:
#             if messagebox.askokcancel("Quit", "Recording in progress. Stop and quit?"):
#                 stop_recording()
#                 time.sleep(1)
#                 root.destroy()
#         else:
#             root.destroy()
    
#     root.protocol("WM_DELETE_WINDOW", on_closing)
#     root.mainloop()


# if __name__ == "__main__":
#     try:
#         import psutil
#     except ImportError:
#         print("Error: psutil not installed. Install it with: pip install psutil")
#         sys.exit(1)
    
#     script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
#     missing = [path for path in SCRIPT_PATHS.values() 
#                if not os.path.exists(os.path.join(script_dir, path))]
#     if missing:
#         print(f"Error: Missing scripts: {', '.join(missing)}")
#         sys.exit(1)
    
#     print("Starting OCTI Meeting Launcher...")
#     create_gui()

