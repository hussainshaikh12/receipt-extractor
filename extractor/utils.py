import base64
import os
import io

import fitz
import pandas as pd
from PIL import Image

from langchain.agents import initialize_agent, AgentType
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import Receipt


GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

def load_document(file_path, mime_type=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if mime_type.startswith('image/'):
        with open(file_path, 'rb') as f:
            content = f.read()

    elif mime_type == 'application/pdf':
        pdf_document = fitz.open(file_path)
        first_page = pdf_document.load_page(0)
        pix = first_page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        content = img_byte_arr.getvalue()
        mime_type = 'image/png'

    elif mime_type.startswith('text/'):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        raise ValueError(f"Unsupported file type: {mime_type}")
    
    return content, mime_type


def process_receipt(file_path, mime_type=None):
    try:
        content, mime_type = load_document(file_path, mime_type)
        llm = ChatGoogleGenerativeAI(model="gemini-pro-vision" if mime_type.startswith('image/') else "gemini-pro", 
                                     google_api_key=GEMINI_API_KEY)

    
        template = """You are a receipt processing expert. Please extract the following information from the receipt content and provide the output in JSON format:
        
            "date": "date on the receipt",
            "vendor": "vendor or store name",
            "total_amount": "total amount"
        
            return Date in the format DD-MM-YYYY, Vendor/Store Name as a string, and Total Amount as a number.
            Always return a single valid JSON format.
            Receipt Content:{content}
        """
        prompt = PromptTemplate(input_variables=["content"], template=template)

    
        if mime_type.startswith('image/'):
            base64_image = base64.b64encode(content).decode('utf-8')
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt.format(content="")},
                    {"type": "image_url", "image_url": f"data:{mime_type};base64,{base64_image}"}
                ]
            )
        else:
            message = HumanMessage(content=prompt.format(content=content))

        response = llm.invoke([message])
        parser = JsonOutputParser()
    
        return parser.parse(response.content)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {}



def process_receipt_query(user, query):

    llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=GEMINI_API_KEY)
    user_receipts = Receipt.objects.filter(user=user)
    df = pd.DataFrame(list(user_receipts.values('date', 'vendor', 'total_amount')))
    python_tool = PythonAstREPLTool(locals={"df": df, "pd": pd})

    agent = initialize_agent(
        [python_tool],
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    prompt_template = PromptTemplate(
        input_variables=["query"],
        template="""
        You are an AI assistant analyzing receipt data for a user. The data is in a pandas DataFrame named 'df' with columns: date, vendor, and total_amount.

        User query: {query}

        To answer this query:
        1. Analyze the 'df' DataFrame using pandas operations.
        2. Provide a detailed response based on your analysis.
        3. If needed, perform calculations, find patterns, or create summaries.
        4. Present the results in a clear, user-friendly format.

        Remember to use pandas functions like df.groupby(), df.sum(), df.mean(), etc., as needed.
        """
    )
    try:
    
        result = agent.invoke(prompt_template.format(query=query))
        # print(result)
        response_content = result.get('output', '')
        return response_content
    
    except Exception as e:
        error_message = f"I encountered an error while processing your query. Here are some tips:\n" \
                        f"1. Try rephrasing your question.\n" \
                        f"2. Make sure you're asking about receipt data (date, vendor, total amount).\n" \
                        f"3. If you're looking for specific calculations, be clear about what you need.\n\n" 
        print(f"Error details: {str(e)}")
        return error_message
