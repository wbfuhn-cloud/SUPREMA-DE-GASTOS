import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time

# Constants
DJI_PATH = r"C:\Program Files (x86)\DJI Product\DJI Assistant 2"
DRIVER_BAT_64 = os.path.join(DJI_PATH, "Drivers_all", "Drivers_Win10", "DriverSetup64.bat")
CACHE_PATH = os.path.join(os.environ.get('APPDATA', ''), 'dji_assistant_2', 'cache') # Typical location

class MavicToolkitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DJI Mavic Pro 1 Toolkit - Professional Maintenance")
        self.root.geometry("600x500")
        self.root.configure(bg="#1e1e1e")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TButton", padding=6, relief="flat", background="#2d2d2d", foreground="white")
        self.style.configure("TLabel", background="#1e1e1e", foreground="white", font=("Segoe UI", 10))
        self.style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"))

        self.setup_ui()
        self.start_monitoring()

    def setup_ui(self):
        # Header
        header = ttk.Label(self.root, text="MAVIC PRO 1 TOOLKIT", font=("Segoe UI", 18, "bold"), foreground="#007acc")
        header.pack(pady=20)

        # Status Frame
        status_frame = ttk.LabelFrame(self.root, text=" Device Status ", padding=10)
        status_frame.pack(padx=20, pady=10, fill="x")
        
        self.status_var = tk.StringVar(value="Checking for device...")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack()

        # Actions Frame
        actions_frame = ttk.LabelFrame(self.root, text=" Maintenance Tools ", padding=10)
        actions_frame.pack(padx=20, pady=10, fill="x")

        ttk.Button(actions_frame, text="Repair USB Drivers (Win10/11)", command=self.repair_drivers).pack(pady=5, fill="x")
        ttk.Button(actions_frame, text="Clear Update Cache", command=self.clear_cache).pack(pady=5, fill="x")
        ttk.Button(actions_frame, text="Launch DJI Assistant 2", command=self.launch_assistant).pack(pady=5, fill="x")

        # Info Frame
        info_frame = ttk.Frame(self.root, padding=10)
        info_frame.pack(side="bottom", fill="x")
        
        ttk.Label(info_frame, text="Note: Use a high-quality data cable and USB 2.0 port if possible.", wraplength=550).pack()

    def repair_drivers(self):
        if not os.path.exists(DRIVER_BAT_64):
            messagebox.showerror("Error", f"Driver setup file not found at:\n{DRIVER_BAT_64}")
            return
        
        try:
            messagebox.showinfo("Drivers", "Attempting to install DJI Drivers. Please allow Admin permissions if requested.")
            subprocess.run(["powershell", "Start-Process", f'"{DRIVER_BAT_64}"', "-Verb", "RunAs"], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run driver installer: {e}")

    def clear_cache(self):
        if not os.path.exists(CACHE_PATH):
            messagebox.showinfo("Cache", "No DJI Assistant 2 cache found. Nothing to clear.")
            return
        
        try:
            # Simple removal of files in cache
            for filename in os.listdir(CACHE_PATH):
                file_path = os.path.join(CACHE_PATH, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            messagebox.showinfo("Success", "DJI Assistant 2 cache cleared successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear cache: {e}")

    def launch_assistant(self):
        exe_path = os.path.join(DJI_PATH, "DJI Assistant 2.exe")
        if os.path.exists(exe_path):
            os.startfile(exe_path)
        else:
            messagebox.showerror("Error", "DJI Assistant 2 executable not found.")

    def start_monitoring(self):
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def monitor_loop(self):
        while True:
            try:
                # Use powershell to check for DJI devices via VID 2ca3
                cmd = 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "2CA3" }'
                output = subprocess.check_output(["powershell", "-Command", cmd]).decode('utf-8')
                
                if "2CA3" in output:
                    self.status_var.set("CONNECTED: DJI Device Detected")
                    self.status_label.configure(foreground="#28a745")
                else:
                    self.status_var.set("DISCONNECTED: Please connect your Mavic/RC")
                    self.status_label.configure(foreground="#dc3545")
            except:
                self.status_var.set("Monitoring Error")
            
            time.sleep(3)

if __name__ == "__main__":
    root = tk.Tk()
    app = MavicToolkitApp(root)
    root.mainloop()
