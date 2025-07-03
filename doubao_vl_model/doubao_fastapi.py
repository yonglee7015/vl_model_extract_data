import os
import base64
import fitz 
from openai import AsyncOpenAI 
import json
import time
import io
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
import tempfile
from typing import List, Dict
import asyncio

app = FastAPI()

# model="doubao-1.5-vision-pro-250328",
model = "doubao-1-5-thinking-vision-pro-250428"
# model="doubao-seed-1-6-250615"

client = AsyncOpenAI(
    api_key=os.getenv("DOUBAO_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

PROMPT_FOLDER = "Doubao Prompts"

def encode_image(image_data: bytes) -> str:
    """Encode image data to a base64 string"""
    return base64.b64encode(image_data).decode('utf-8')

async def pdf_to_images(pdf_path: str) -> List[bytes]:
    """Convert a PDF to a list of images (use thread pool to handle CPU-intensive tasks)"""
    images = []
    # Execute the synchronous fitz.open in a thread pool
    try:
        doc = await asyncio.to_thread(fitz.open, pdf_path)
        
        # Process each page (can also put each page processing in a thread pool)
        for page_num in range(len(doc)):
            # Also put get_pixmap and image processing in a thread pool
            page = doc.load_page(page_num)
            pix = await asyncio.to_thread(page.get_pixmap, dpi=300)
            
            # Use Pillow to process the image (CPU-intensive operation)
            img = await asyncio.to_thread(
                Image.frombytes, 
                "RGB", 
                [pix.width, pix.height], 
                pix.samples
            )
            
            img_byte_arr = io.BytesIO()
            await asyncio.to_thread(img.save, img_byte_arr, format='PNG', quality=80)
            images.append(img_byte_arr.getvalue())
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(e)}"
        )
    finally:
        if 'doc' in locals():
            await asyncio.to_thread(doc.close)
    
    return images

def get_prompt_by_doc_type(doc_type: str) -> str:
    """
    Get the corresponding prompt based on the document type
    """
    keyword = doc_type.replace(" ", "_").lower()
    for root, _, files in os.walk(PROMPT_FOLDER):
        for file in files:
            if keyword in file.lower():
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
    print(f"No prompt file found for document type: {doc_type}")
    return ""

async def classify_document_type(image_contents: List[Dict]) -> str:
    """Asynchronously classify the document type"""
    try:
        doc_type_completion = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an AI specialized in analyzing images of documents. Analyze the provided image and identify the document type based on the given rules."
                }, 
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text", 
                            "text": "Identify the document type. The possible types are 'PO', 'invoice', 'sea waybill', 'air waybill', 'others'. Return only one of these types."
                        },
                        *image_contents
                    ]
                }
            ],
            max_tokens=1024
        )
        return doc_type_completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document classification failed: {str(e)}")

async def process_document(system_prompt: str, image_contents: List[Dict], doc_type: str) -> Dict:
    """Asynchronously process the document and extract data"""
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": system_prompt
                }, 
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text", 
                            "text": f"The document type is {doc_type}. Extract data from the image and return the result in JSON format."
                        },
                        *image_contents
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=8192
        )
        return json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON parsing failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


async def process_single_pdf(file: UploadFile) -> dict:
    """
    Independent function: Process a single PDF file
    Returns: {
        "filename": str,
        "result": dict | None,
        "error": str | None,
        "processing_time": float
    }
    """
    start_time = time.time()
    temp_pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            await file.seek(0)  # Ensure the file pointer is at the beginning
            temp_pdf.write(await file.read())
            temp_pdf_path = temp_pdf.name

        pdf_images = await pdf_to_images(temp_pdf_path)
        
        image_contents = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(img)}"}
            } 
            for img in pdf_images
        ]

        doc_type = await classify_document_type(image_contents)
        system_prompt = get_prompt_by_doc_type(doc_type)
        if not system_prompt:
           return {
                "doc_type": doc_type,
                "filename": file.filename,
                "result": {},
                "error": "No prompt template found for document type",
                "processing_time": time.time() - start_time
            }

        result = await process_document(system_prompt, image_contents, doc_type)
        
        json_path = f"{os.path.splitext(file.filename)[0]}.json"
        await asyncio.to_thread(lambda: json.dump(result, open(json_path, "w"), indent=2))
        
        return {
            "doc_type": doc_type,
            "filename": file.filename,
            "result": result,
            "error": None,
            "processing_time": time.time() - start_time
        }
        
    except Exception as e:
        import logging
        logging.error(f"Error processing file {file.filename}: {str(e)}")
        return {
            "doc_type": doc_type,
            "filename": file.filename,
            "result": None,
            "error": str(e),
            "processing_time": time.time() - start_time
        }
    finally:
        if temp_pdf_path:
            try:
                os.remove(temp_pdf_path)
            except Exception as rm_e:
                logging.error(f"Error removing temporary file {temp_pdf_path}: {str(rm_e)}")

@app.post("/process_pdfs/")
async def batch_process_pdfs(files: List[UploadFile] = File(...)):
    """
    Batch processing entry point
    """
    semaphore = asyncio.Semaphore(5) 

    async def process_with_semaphore(file):
        async with semaphore:
            return await process_single_pdf(file)

    tasks = [process_with_semaphore(file) for file in files]
    results = await asyncio.gather(*tasks)

    return {
        "total_files": len(files),
        "success_count": sum(1 for r in results if r["error"] is None),
        "failed_count": sum(1 for r in results if r["error"] is not None),
        "results": results
    }