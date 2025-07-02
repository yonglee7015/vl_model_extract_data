import os
import base64
import fitz 
from openai import OpenAI
import json
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import webbrowser
import time
import io
from PIL import Image


# model="doubao-1.5-vision-pro-250328",
model="doubao-1-5-thinking-vision-pro-250428"
# model="doubao-seed-1-6-250615"

client = OpenAI(
    api_key=os.getenv("DOUBAO_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

system_prompt = ""
pdf_file_path = ""
start_time = None
timer_running = False
timer_label = None
prompt_file_path = "" 


def load_prompt_file():
    global system_prompt
    if prompt_file_path:
        with open(prompt_file_path, "r", encoding="utf-8") as file:
            system_prompt = file.read()
        prompt_label.config(text=f"Selected prompt file: {os.path.basename(prompt_file_path)}")


def select_prompt_file():
    global prompt_file_path
    file_path = filedialog.askopenfilename(title="Select System Prompt File", filetypes=[("Text Files", "*.txt")])
    if file_path:
        prompt_file_path = file_path
        load_prompt_file()

def select_pdf_file():
    global pdf_file_path
    file_path = filedialog.askopenfilename(title="Select PDF File", filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        pdf_file_path = file_path
        pdf_label.config(text=f"Selected PDF file: {os.path.basename(file_path)}")
        load_prompt_file()

def encode_image(image_data):
    return base64.b64encode(image_data).decode('utf-8')

# def pdf_to_images(pdf_path):
#     doc = fitz.open(pdf_path)
#     images = []
#     for page_num in range(len(doc)):
#         page = doc.load_page(page_num)
#         pix = page.get_pixmap(dpi=300)
#         images.append(pix.tobytes())
#     doc.close()
#     return images


def pdf_to_images(pdf_path):
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG', quality=80)  # 调整质量参数
        img_byte_arr = img_byte_arr.getvalue()
        images.append(img_byte_arr)
    doc.close()
    return images

def open_json_file(event):
    json_file_path = event.widget.json_file_path
    if os.path.exists(json_file_path):
        webbrowser.open(os.path.abspath(json_file_path))

def update_timer():
    if timer_running:
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        timer_label.config(text=f"Elapsed Time: {minutes:02d}:{seconds:02d}")
        root.after(1000, update_timer)

def processing_task():
    global start_time, timer_running
    if not system_prompt or not pdf_file_path:
        style.configure('Error.TLabel', foreground='red')
        status_label.grid() 
        root.after(0, lambda: status_label.config(text="Please select a prompt file and a PDF file", style='Error.TLabel'))
        return

    start_time = time.time()
    timer_running = True
    status_label.grid()
    timer_label.grid()
    update_timer()

    pdf_images = pdf_to_images(pdf_file_path)

    # Get the PDF file name (without extension)
    pdf_file_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
    json_file_path = f"{pdf_file_name}.json"

    # Build the message content containing all images
    image_contents = []
    for image_data in pdf_images:
        base64_image = encode_image(image_data)
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
        })

    style.configure('Processing.TLabel', foreground='blue')
    root.after(0, lambda: status_label.config(text="Processing...", style='Processing.TLabel'))

    try:
        # Enable streaming by setting stream=True
        completion = client.chat.completions.create(
            model= model,
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract data from the image and return the result in JSON format."},
                    *image_contents
                ]}
            ],
            response_format={
                    'type': 'json_object'
                },
            max_tokens=8192,
            stream=True  # Enable streaming
            
        )

        result_chunks = []
        # Iterate over the streamed chunks
        for chunk in completion:
            if chunk.choices[0].delta.content:
                result_chunks.append(chunk.choices[0].delta.content)
        result = ''.join(result_chunks)
        print(result)

        try:
            data = json.loads(result)
            with open(json_file_path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, ensure_ascii=False, indent=4)
            style.configure('Success.TLabel', foreground='green', font=('Helvetica', 10, 'underline'))
            status_label.json_file_path = json_file_path
            status_label.bind("<Button-1>", open_json_file)
            status_label.bind("<Enter>", lambda e: root.config(cursor="hand2"))
            status_label.bind("<Leave>", lambda e: root.config(cursor=""))
            root.after(0, lambda: status_label.config(text=f"OCR results for all pages have been saved to {json_file_path}", style='Success.TLabel'))
        except json.JSONDecodeError as e:
            style.configure('Error.TLabel', foreground='red')
            # Pass the exception as an argument to the lambda function
            root.after(0, lambda err=e: status_label.config(text=f"JSON parsing failed: {err}", style='Error.TLabel'))
    except Exception as e:
        style.configure('Error.TLabel', foreground='red')
        # Pass the exception as an argument to the lambda function
        root.after(0, lambda err=e: status_label.config(text=f"An error occurred during processing: {err}", style='Error.TLabel'))
    finally:
        timer_running = False

def start_processing():
    # Execute time-consuming operations in a new thread
    threading.Thread(target=processing_task, daemon=True).start()

root = tk.Tk()
root.title("Model Doubao: File Selection and Processing")

# Set window width and height
window_width = 600
window_height = 250

# Get screen width and height
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Calculate the x and y coordinates of the window on the screen
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2

# Set the size and position of the window
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Configure ttk style
style = ttk.Style()
style.theme_use('clam')
style.configure('TButton', padding=6, relief='flat', background='#4CAF50', foreground='white')
style.map('TButton', background=[('active', '#45a049')])
style.configure('TLabel', padding=6, font=('Helvetica', 10))

# Create and place widgets using grid layout
prompt_button = ttk.Button(root, text="Select Prompt File", command=select_prompt_file)
prompt_button.grid(row=0, column=0, padx=10, pady=10, sticky='ew')

prompt_label = ttk.Label(root, text="No prompt file selected")
prompt_label.grid(row=0, column=1, padx=10, pady=10, sticky='w')

pdf_button = ttk.Button(root, text="Select PDF File", command=select_pdf_file)
pdf_button.grid(row=1, column=0, padx=10, pady=10, sticky='ew')

pdf_label = ttk.Label(root, text="No PDF file selected")
pdf_label.grid(row=1, column=1, padx=10, pady=10, sticky='w')

start_button = ttk.Button(root, text="Start Processing", command=start_processing)
start_button.grid(row=2, column=0, columnspan=2, padx=10, pady=(10, 0), sticky='ew')

status_label = ttk.Label(root, text="")
# 初始隐藏状态标签
status_label.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky='w')
status_label.grid_remove()

timer_label = ttk.Label(root, text="Elapsed Time: 00:00")
# 初始隐藏计时器标签，放置在 status_label 下方
timer_label.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky='w')
timer_label.grid_remove()

# Configure column weights to make buttons expand
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=3)

root.mainloop()