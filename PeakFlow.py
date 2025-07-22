import sounddevice as sd
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox,PhotoImage
import os
import webbrowser
import pygame
import sys

# ==== PARAMETERS ====
sample_rate = 48000
block_size = 1024
initial_limit_db = -10
input_device = 2  # Example: VB-Audio Virtual Cable
# Initialize pygame mixer for audio playback
pygame.mixer.init()


# Variable to track playback state
is_playing_test = False

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ==== UTILS ====
def db_to_amplitude(db):
    return 10 ** (db / 20)

def amplitude_to_db(amp):
    return 20 * np.log10(amp + 1e-6)

def is_vb_cable_installed():
    try:
        devices = sd.query_devices()
        for dev in devices:
            name = dev.get('name', '').lower()
            if 'vb-audio' in name or 'vb-cable' in name:
                return True
        return False
    except Exception as e:
        print(f"Error checking audio devices: {e}")
        return False

def open_vb_audio_site():
    webbrowser.open("https://vb-audio.com/Cable/")

def open_windows_sound_settings():
    try:
        os.system("start ms-settings:sound")
    except Exception as e:
        messagebox.showerror("Error", f"Unable to open Windows Sound settings.\n{e}")

# ==== AUDIO PROCESSING ====
def hard_limiter(audio, threshold):
    return np.clip(audio, -threshold, threshold)

def soft_compressor(audio, threshold_db, ratio=4.0, knee_db=6.0):
    threshold_amp = db_to_amplitude(threshold_db)
    knee_amp = db_to_amplitude(knee_db)
    abs_audio = np.abs(audio)
    gain = np.ones_like(audio)

    for i, a in enumerate(abs_audio):
        if a < threshold_amp - knee_amp / 2:
            gain[i] = 1.0
        elif a > threshold_amp + knee_amp / 2:
            gain[i] = threshold_amp / (a + 1e-9) ** (1 - 1 / ratio)
        else:
            x = (a - (threshold_amp - knee_amp / 2)) / knee_amp
            soft_gain = threshold_amp / (a + 1e-9) ** (1 - 1 / ratio)
            gain[i] = 1.0 + (soft_gain - 1.0) * x ** 2 * (3 - 2 * x)

    return audio * gain

def audio_callback(indata, outdata, frames, time, status):
    global max_in_amp, max_out_amp
    if status:
        print(status)
    audio = indata[:, 0]
    max_in_amp[0] = np.max(np.abs(audio))

    threshold_db = current_threshold_db[0]

    if mode_setting.get() == "automatic":
        if threshold_db > -25:
            processed = hard_limiter(audio, db_to_amplitude(threshold_db))
        else:
            processed = soft_compressor(audio, threshold_db)
    else:
        if selected_mode.get() == "Limiter":
            processed = hard_limiter(audio, db_to_amplitude(threshold_db))
        else:
            processed = soft_compressor(audio, threshold_db)

    max_out_amp[0] = np.max(np.abs(processed))
    outdata[:, 0] = processed
    outdata[:, 1] = processed

# ==== STREAM CONTROL ====
def start_audio_stream():
    global stream
    stop_audio_stream()

    if not is_vb_cable_installed():
        print("VB-Audio Cable not installed. Audio stream not started.")
        return  # Skip starting the stream

    try:
        selected = output_device_var.get()
        if selected == "(Default Windows Output)":
            out_dev = None
        else:
            out_dev = int(selected.split(" - ")[0])

        stream = sd.Stream(
            samplerate=sample_rate,
            blocksize=block_size,
            device=(input_device, out_dev),
            channels=(1, 2),
            dtype='float32',
            callback=audio_callback)
        stream.start()
    except Exception as e:
        messagebox.showerror("Stream Error", f"Error: {e}")
        stream = None

def stop_audio_stream():
    global stream
    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception as e:
            print(f"Error closing stream: {e}")
        stream = None

def on_output_device_change(event):
    start_audio_stream()

def list_output_devices(show_all=False):
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    mme_id = next((i for i, h in enumerate(hostapis) if h['name'].lower().startswith('mme')), None)

    outputs = []
    for i, dev in enumerate(devices):
        if dev['max_output_channels'] > 0 and dev['default_samplerate'] > 0:
            if show_all or (mme_id is not None and dev['hostapi'] == mme_id):
                outputs.append((i, dev['name']))
    return outputs

def refresh_device_list():
    selected = output_device_var.get()
    show_all = show_all_var.get()
    new_devices = list_output_devices(show_all=show_all)
    output_device_choices = ["(Default Windows Output)"] + [f"{i} - {name}" for i, name in new_devices]
    output_device_dropdown['values'] = output_device_choices

    if selected in output_device_choices:
        output_device_var.set(selected)
    else:
        if new_devices:
            output_device_var.set(f"{new_devices[0][0]} - {new_devices[0][1]}")
        else:
            output_device_var.set("(Default Windows Output)")

    start_audio_stream()

# ==== GUI CALLBACKS ====
def update_threshold(val):
    db = float(val)
    current_threshold_db[0] = db
    label_var.set(f"Threshold: {db:.1f} dBFS")

def update_meter():
    in_db = amplitude_to_db(max_in_amp[0])
    out_db = amplitude_to_db(max_out_amp[0])
    reduction = max(0.0, in_db - out_db)
    vu_label.config(text=f"Input: {in_db:.1f} dBFS | Output: {out_db:.1f} dBFS")
    gain_label.config(text=f"Gain Reduction: {reduction:.1f} dB")
    root.after(100, update_meter)

def update_mode_visibility():
    if mode_setting.get() == "custom":
        limiter_radio.pack()
        compressor_radio.pack()
    else:
        limiter_radio.pack_forget()
        compressor_radio.pack_forget()

def update_setup_ui():
    if is_vb_cable_installed():
        startup_label.config(
            text=(
                "✅ VB-Audio Virtual Cable is detected.\n"
                "Make sure your Windows output is set to: VB-Audio Cable.\n"
                "Click the button below to open Windows Sound Settings.\n\n"
                "Choose the correct audio output (speakers or headset). If there is still no sound, make sure you restarted your PC after installing VB-Audio Cable."
            ),
            foreground="green"
        )
        installer_btn.config(text="Open Windows Sound Settings", command=open_windows_sound_settings)
    else:
        startup_label.config(
            text=(
                "⚠️ VB-Audio Virtual Cable is not detected!\n\n"
                "1. Visit the official website.\n"
                "2. Download and extract the ZIP.\n"
                "3. Run the installer as Administrator.\n"
                "4. Restart your PC.\n"
                "5. Set Windows output to VB-Audio Cable manually."
            ),
            foreground="red"
        )
        installer_btn.config(text="Install VB-Audio Cable", command=open_vb_audio_site)

# ==== VARIABLES ====
current_threshold_db = [initial_limit_db]
max_in_amp = [0.0]
max_out_amp = [0.0]
stream = None

# ==== GUI SETUP ====
root = tk.Tk()
root.title("Peak Flow")

icon_path = os.path.join(os.path.dirname(sys.argv[0]), "logo.png")
try:
    icon_img = PhotoImage(file=icon_path)
    root.iconphoto(True, icon_img)
except Exception as e:
    print(f"Failed to set window icon: {e}")

# Section 1: Warning and Installer
startup_frame = ttk.LabelFrame(root, text="Setup")
startup_frame.pack(fill="x", padx=10, pady=5)

startup_label = ttk.Label(startup_frame, wraplength=400, justify="left")
startup_label.pack(padx=10, pady=5)

installer_btn = ttk.Button(startup_frame)
installer_btn.pack(pady=5)

update_setup_ui()

## Section 2: Compressor
compressor_frame = ttk.LabelFrame(root, text="Compressor Settings")
compressor_frame.pack(fill="x", padx=10, pady=5)

label_var = tk.StringVar()
label = ttk.Label(compressor_frame, textvariable=label_var)
label.pack()

slider = ttk.Scale(compressor_frame, from_=-1, to=-40, orient="horizontal", command=update_threshold)
slider.set(initial_limit_db)
slider.pack(fill="x", padx=10)

vu_label = ttk.Label(compressor_frame, text="Input: 0.0 | Output: 0.0")
vu_label.pack()

gain_label = ttk.Label(compressor_frame, text="Gain Reduction: 0.0 dB")
gain_label.pack()

mode_setting = tk.StringVar(value="automatic")
mode_auto_radio = ttk.Radiobutton(compressor_frame, text="Automatic (Default)", variable=mode_setting, value="automatic", command=update_mode_visibility)
mode_custom_radio = ttk.Radiobutton(compressor_frame, text="Custom", variable=mode_setting, value="custom", command=update_mode_visibility)
mode_auto_radio.pack()
mode_custom_radio.pack()

selected_mode = tk.StringVar(value="Limiter")
limiter_radio = ttk.Radiobutton(compressor_frame, text="Limiter", variable=selected_mode, value="Limiter")
compressor_radio = ttk.Radiobutton(compressor_frame, text="Compressor", variable=selected_mode, value="Compressor")

# Section 3: Output device
device_frame = ttk.LabelFrame(root, text="Audio Output")
device_frame.pack(fill="x", padx=10, pady=5)

output_device_label = ttk.Label(device_frame, text="Select Output Device:")
output_device_label.pack()

show_all_var = tk.BooleanVar(value=False)
show_all_checkbox = ttk.Checkbutton(device_frame, text="Show all audio devices", variable=show_all_var, command=refresh_device_list)
show_all_checkbox.pack()

output_device_var = tk.StringVar()
output_device_dropdown = ttk.Combobox(device_frame, state="readonly", textvariable=output_device_var, width=60)
output_device_dropdown.pack(padx=10, pady=(0, 10))
output_device_dropdown.bind("<<ComboboxSelected>>", on_output_device_change)

# ==== INIT ====
refresh_device_list()
slider.set(initial_limit_db)
update_mode_visibility()
root.after(100, update_meter)

icon_path = resource_path("logo.png")

# Show warning popup if VB-Audio not installed
if not is_vb_cable_installed():
    root.after(500, lambda: messagebox.showwarning(
        "VB-Audio Cable Not Detected",
        "VB-Audio Virtual Cable is required for this application to work properly.\n\n"
        "Visit https://vb-audio.com/Cable/, install the driver, restart your PC,\n"
        "and set your Windows output device to VB-Audio Cable."
    ))


root.mainloop()
