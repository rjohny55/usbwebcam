import cv2
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
import queue
import time
import datetime
import os
import usb.core
import usb.util

import cv2
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
import queue
import time
import datetime
import os
import usb.core
import usb.util

class VideoRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("2M WebCam Recorder Pro")
        
        # Инициализируем камеры
        self.available_cameras = self.detect_usb_cameras()  # <-- Теперь метод доступен
        if not self.available_cameras:
            print("Ошибка: Не найдено ни одной камеры!")
            exit()

        self.resolutions = [
            (1280, 720),   # 1.3MP
            (1920, 1080)   # 2MP
        ]
        
        self.codecs = [
            ('H.264 (.mp4)', 'avc1', 'mp4'),
            ('MPEG-4 (.mp4)', 'mp4v', 'mp4'),
            ('X264 (.mp4)', 'X264', 'mp4'),
            ('MJPG (.avi)', 'MJPG', 'avi'),
            ('XVID (.avi)', 'XVID', 'avi')
        ]
        
        self.quality_presets = {
            'Плохое': 0.5,
            'Среднее': 1.0,
            'Лучшее': 2.0
        }
        
        self.base_bitrates = {
            (1280, 720): 4000,
            (1920, 1080): 8000
        }
        
        self.current_camera = self.available_cameras[0]['index']
        self.current_res = self.resolutions[0]
        self.current_quality = 'Среднее'
        self.preview_size = self.calculate_preview_size(self.current_res)
        self.current_codec = self.codecs[0]
        self.frame_rate = 30
        self.is_recording = False
        self.stop_thread = False
        self.output_file = ""
        self.out = None
        self.start_time = None
        self.last_sync = time.time()
        self.frame_count = 0
        self.lock = threading.Lock()
        
        self.create_widgets()
        self.frame_queue = queue.Queue(maxsize=1)
        self.video_thread = threading.Thread(target=self.video_capture_thread)
        self.video_thread.start()
        self.update_gui()

    def detect_usb_cameras(self):
        cameras = []
        index = 0
        while True:
            cap = cv2.VideoCapture(index)
            if not cap.read()[0]:
                cap.release()
                break
            
            device_info = {
                'index': index,
                'name': f"Неизвестная камера ({index})",
                'vendor_id': "0000",
                'product_id': "0000",
            }
            
            try:
                for d in usb.core.find(find_all=True):
                    if d.bDeviceClass == 0x0e:
                        try:
                            manufacturer = usb.util.get_string(d, d.iManufacturer) or "Unknown"
                            product = usb.util.get_string(d, d.iProduct) or ""
                            
                            device_info.update({
                                'vendor_id': f"{d.idVendor:04x}",
                                'product_id': f"{d.idProduct:04x}",
                                'name': f"{manufacturer} {product}",
                                
                            })
                            if serial:
                                device_info['name'] 
                            break
                        except:
                            continue
            except Exception as e:
                print(f"Ошибка USB: {str(e)}")
            
            cameras.append(device_info)
            cap.release()
            index += 1
        
        unique_cameras = []
        seen = set()
        for cam in cameras:
            key = f"{cam['vendor_id']}:{cam['product_id']}"
            if key not in seen:
                seen.add(key)
                unique_cameras.append(cam)
        
        return unique_cameras

   
    def calculate_preview_size(self, resolution):
        max_width = 640
        width, height = resolution
        aspect_ratio = width / height
        new_width = min(width, max_width)
        return (new_width, int(new_width / aspect_ratio))

    def create_widgets(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        self.camera_combo = ttk.Combobox(
            control_frame,
            values=[f"{cam['name']} [VID:{cam['vendor_id']} PID:{cam['product_id']}]" 
                   for cam in self.available_cameras],
            state="readonly",
            width=40
        )
        self.camera_combo.current(0)
        self.camera_combo.bind("<<ComboboxSelected>>", self.update_camera)
        self.camera_combo.pack(side=tk.LEFT, padx=5)
        
        self.res_combo = ttk.Combobox(
            control_frame,
            values=[f"{w}x{h} ({w*h/1e6:.1f}MP)" for w, h in self.resolutions],
            state="readonly",
            width=18
        )
        self.res_combo.current(0)
        self.res_combo.bind("<<ComboboxSelected>>", self.update_resolution)
        self.res_combo.pack(side=tk.LEFT, padx=5)
        
        self.codec_combo = ttk.Combobox(
            control_frame,
            values=[name for name, _, _ in self.codecs],
            state="readonly",
            width=15
        )
        self.codec_combo.current(0)
        self.codec_combo.bind("<<ComboboxSelected>>", self.update_codec)
        self.codec_combo.pack(side=tk.LEFT, padx=5)
        
        self.quality_combo = ttk.Combobox(
            control_frame,
            values=list(self.quality_presets.keys()),
            state="readonly",
            width=10
        )
        self.quality_combo.current(1)
        self.quality_combo.bind("<<ComboboxSelected>>", self.update_quality)
        self.quality_combo.pack(side=tk.LEFT, padx=5)
        
        self.rec_btn = ttk.Button(
            control_frame,
            text="Начать запись",
            command=self.toggle_recording
        )
        self.rec_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = ttk.Button(
            control_frame,
            text="Выход",
            command=self.safe_exit
        )
        exit_btn.pack(side=tk.LEFT, padx=5)
        
        self.video_label = tk.Label(self.root)
        self.video_label.pack(padx=10, pady=10)
        
        self.status_bar = ttk.Label(self.root, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def calculate_bitrate(self):
        base_bitrate = self.base_bitrates[self.current_res]
        return int(base_bitrate * self.quality_presets[self.current_quality])

    def video_capture_thread(self):
        cap = None
        prev_settings = (None, None, None)
        while not self.stop_thread:
            try:
                with self.lock:
                    current_settings = (
                        self.current_camera,
                        self.current_res,
                        self.preview_size
                    )
                
                if prev_settings != current_settings:
                    if cap is not None:
                        cap.release()
                    cap = cv2.VideoCapture(current_settings[0])
                    if not cap.isOpened():
                        raise RuntimeError("Ошибка инициализации камеры")
                    
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, current_settings[1][0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, current_settings[1][1])
                    cap.set(cv2.CAP_PROP_FPS, self.frame_rate)
                    
                    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if (actual_width, actual_height) != current_settings[1]:
                        self.update_status(f"Фактическое разрешение: {actual_width}x{actual_height}")
                    
                    prev_settings = current_settings
                
                ret, frame = cap.read()
                if not ret:
                    raise RuntimeError("Ошибка захвата кадра")
                
                if self.is_recording and self.out is not None:
                    try:
                        self.out.write(frame)
                        self.frame_count += 1
                        
                        if time.time() - self.last_sync > 2:
                            os.sync() if hasattr(os, 'sync') else None
                            self.last_sync = time.time()
                    except Exception as e:
                        self.update_status(f"Ошибка записи: {str(e)}")
                        self.stop_recording()
                
                resized = cv2.resize(frame, prev_settings[2])
                img = ImageTk.PhotoImage(image=Image.fromarray(
                    cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))
                
                if self.frame_queue.empty():
                    self.frame_queue.put_nowait(img)
            
            except Exception as e:
                self.update_status(f"Ошибка: {str(e)}")
                if cap is not None:
                    cap.release()
                    cap = None
                time.sleep(1)
        
        if cap is not None:
            cap.release()
        if self.out is not None:
            self.out.release()

    def update_camera(self, event):
        selected = self.camera_combo.current()
        with self.lock:
            self.current_camera = self.available_cameras[selected]['index']
        self.update_status(f"Выбрана камера: {self.available_cameras[selected]['name']}")

    def update_resolution(self, event):
        with self.lock:
            new_res = self.resolutions[self.res_combo.current()]
            self.current_res = new_res
            self.preview_size = self.calculate_preview_size(new_res)
        self.res_combo.config(state="disabled")
        self.root.after(500, lambda: self.res_combo.config(state="readonly"))
        self.update_status(f"Установлено разрешение: {new_res[0]}x{new_res[1]}")

    def update_codec(self, event):
        self.current_codec = self.codecs[self.codec_combo.current()]
        self.update_status(f"Выбран кодек: {self.current_codec[0]}")

    def update_quality(self, event):
        self.current_quality = self.quality_combo.get()
        self.update_status(f"Качество: {self.current_quality}")

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        save_dir = filedialog.askdirectory(title="Выберите папку для сохранения")
        if not save_dir:
            return
        
        try:
            test_path = os.path.join(save_dir, "write_test.tmp")
            with open(test_path, "w") as f:
                f.write("test")
            os.remove(test_path)
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            target_bitrate = self.calculate_bitrate() * 1000
            success = False
            
            for codec in [self.current_codec] + [c for c in self.codecs if c != self.current_codec]:
                codec_name, fourcc_code, ext = codec
                try:
                    output_file = os.path.join(save_dir, f"video_{timestamp}.{ext}")
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                    if fourcc == -1:
                        continue
                    
                    out = cv2.VideoWriter(
                        output_file,
                        fourcc,
                        self.frame_rate,
                        self.current_res,
                        True
                    )
                    
                    if out.isOpened():
                        try:
                            out.set(cv2.VIDEOWRITER_PROP_BITRATE, target_bitrate)
                        except:
                            pass
                        
                        self.output_file = output_file
                        self.out = out
                        success = True
                        if codec != self.current_codec:
                            self.update_status(f"Используется кодек: {codec_name} (резервный)")
                        break
                except:
                    continue
            
            if not success:
                raise RuntimeError("Не удалось инициализировать запись")
            
            self.is_recording = True
            self.start_time = time.time()
            self.rec_btn.config(text="Остановить запись")
            self.disable_controls(True)
            self.update_status_timer()
            self.update_status(f"Начата запись: {os.path.basename(self.output_file)}")
            
        except Exception as e:
            self.update_status(f"Ошибка: {str(e)}")
            self.stop_recording()

    def stop_recording(self):
        self.is_recording = False
        if self.out is not None:
            try:
                self.out.release()
            except:
                pass
            self.out = None
        
        if os.path.exists(self.output_file):
            size = os.path.getsize(self.output_file)
            if size > 2048:
                self.update_status(f"Файл сохранен: {self.output_file} ({size//1024} KB)")
            else:
                os.remove(self.output_file)
                self.update_status("Ошибка: Файл слишком мал")
        else:
            self.update_status("Ошибка: Файл не создан")
        
        self.rec_btn.config(text="Начать запись")
        self.disable_controls(False)

    def disable_controls(self, disable):
        state = "disabled" if disable else "readonly"
        self.camera_combo.config(state=state)
        self.res_combo.config(state=state)
        self.codec_combo.config(state=state)
        self.quality_combo.config(state=state)

    def update_status_timer(self):
        if self.is_recording:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            size = os.path.getsize(self.output_file) if os.path.exists(self.output_file) else 0
            status_text = (
                f"{self.current_codec[0]} | {self.current_res[0]}x{self.current_res[1]} | "
                f"{self.current_quality} ({self.calculate_bitrate()}kbps) | "
                f"{mins:02d}:{secs:02d} | {size//1024} KB"
            )
            self.status_bar.config(text=status_text)
            self.root.after(1000, self.update_status_timer)

    def update_gui(self):
        try:
            frame = self.frame_queue.get_nowait()
            self.video_label.configure(image=frame)
            self.video_label.image = frame
        except queue.Empty:
            pass
        
        if not self.stop_thread:
            self.root.after(10, self.update_gui)

    def safe_exit(self):
        self.stop_thread = True
        self.is_recording = False
        
        if self.out is not None:
            self.out.release()
        
        if self.video_thread.is_alive():
            self.video_thread.join(timeout=1)
        
        self.root.destroy()

    def update_status(self, message):
        self.status_bar.config(text=message)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoRecorderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()