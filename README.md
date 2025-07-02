# Doubao Vision API Tool

A GUI application for processing PDF files using the Doubao Vision API and extracting data in JSON format.

## Features
- Select a system prompt text file to guide the API processing
- Choose a PDF file for data extraction
- Convert PDF pages to images with adjustable quality
- Stream API responses for efficient processing
- Save extracted data as JSON with clickable link to open the file
- Timer to track processing duration

## Requirements
- Python 3.x
- Required packages:
  - `openai`
  - `fitz` (PyMuPDF)
  - `Pillow`
  - `tkinter` (usually included with Python)
- Doubao API key set as environment variable `DOUBAO_API_KEY`

## Installation
Install the required packages using pip:
```
pip install openai pymupdf Pillow
```

## Usage
1. Run the script: `python doubao_vl_api_stream.py`
2. Click "Select Prompt File" to choose a text file containing the system prompt
3. Click "Select PDF File" to choose the PDF you want to process
4. Click "Start Processing" to begin the extraction
5. The application will:
   - Convert each PDF page to an image
   - Send the images to the Doubao Vision API
   - Stream the response and save as JSON
6. When complete, click the status message to open the generated JSON file

## Configuration
The script supports different Doubao models. You can modify the `model` variable in the script:
```
# model="doubao-1.5-vision-pro-250328",
model="doubao-1-5-thinking-vision-pro-250428"
# model="doubao-seed-1-6-250615"
```

## Notes
- The application uses a streaming API connection for better performance with large documents
- PDF pages are converted to PNG images with DPI=300 by default
- The JSON output is formatted with indentation for readability
- Error messages will appear in red if processing fails

## License
This project is open source and available for use under the MIT License.