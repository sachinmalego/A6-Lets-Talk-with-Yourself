from flask import Flask, render_template, request, jsonify
import torch
from transformers import AutoTokenizer, pipeline, AutoModelForSeq2SeqLM
from langchain import PromptTemplate
from langchain_community.embeddings import HuggingFaceInstructEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import LLMChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import ConversationalRetrievalChain
from langchain import HuggingFacePipeline
import warnings
import logging

warnings.simplefilter("ignore", FutureWarning)

app = Flask(__name__)

# Set device
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

# Load vector database
DB_FILE_NAME = '/Users/sachinmalego/Documents/AIT Course Works/02. Second Semester/02. AI-NLU/Lab Work/Github/Python-fo-Natural-Language-Processing/Assignment/NLP-A6-Lets-Talk-with-Yourself/vector-store/nlp_db'
EMB_MODEL_NAME = 'hkunlp/instructor-base'
MODEL_ID = '/Users/sachinmalego/Documents/AIT Course Works/02. Second Semester/02. AI-NLU/Lab Work/Github/Python-fo-Natural-Language-Processing/Assignment/NLP-A6-Lets-Talk-with-Yourself/models/fastchat-t5-3b-v1.0'

# Define the prompt
prompt_template = """
    Hi! I am an AI assistant RAGBot that answers questions based on available documents.
    I ensure responses are accurate and cite relevant sources.
    Context: {context}
    Question: {question}
    Answer:
""".strip()

PROMPT = PromptTemplate.from_template(template=prompt_template)

# Load embeddings
embedding_model = HuggingFaceInstructEmbeddings(
    model_name=EMB_MODEL_NAME,
    model_kwargs={"device": device}
)

# Load FAISS vector database
try:
    vectordb = FAISS.load_local(
        folder_path=DB_FILE_NAME,
        embeddings=embedding_model,
        index_name='nlp'
    )
    retriever = vectordb.as_retriever()
except Exception as e:
    logging.error(f"Error loading FAISS database: {e}")
    vectordb, retriever = None, None

# Load model & tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
tokenizer.pad_token_id = tokenizer.eos_token_id

model = AutoModelForSeq2SeqLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map={"": device}
)

pipe = pipeline(
    task="text2text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=512,  # Adjusted tokens
    model_kwargs={"temperature": 0.3, "repetition_penalty": 1.5}
)

llm = HuggingFacePipeline(pipeline=pipe)

# Setup chains
question_generator = LLMChain(
    llm=llm,
    prompt=CONDENSE_QUESTION_PROMPT,
    verbose=True
)

doc_chain = load_qa_chain(
    llm=llm,
    chain_type='stuff',
    prompt=PROMPT,
    verbose=True
)

memory = ConversationBufferWindowMemory(
    k=3,
    memory_key="chat_history",
    return_messages=True,
    output_key='answer'
)

if retriever:
    chain = ConversationalRetrievalChain(
        retriever=retriever,
        question_generator=question_generator,
        combine_docs_chain=doc_chain,
        return_source_documents=True,
        memory=memory,
        verbose=True,
        get_chat_history=lambda h: h
    )

import logging

@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.is_json:  # This handles the AJAX case
            prompt_question = request.json.get('prompt_question')

            # List of common courtesy words (greetings, thanks, etc.)
            courtesy_words = [
                'hi', 'hello', 'hey', 'hi there', 'hello there', 'hey there',
                'howdy', 'good morning', 'good evening', 'good night',
                'thanks', 'thank you', 'thank you very much', 'thanks a lot',
                'appreciate it', 'many thanks', 'you\'re welcome', 'sorry',
                'excuse me', 'please'
            ]
            
            # If the prompt contains a courtesy word, but not a real question, respond with a greeting
            if any(courtesy_word in prompt_question.lower() for courtesy_word in courtesy_words) and '?' not in prompt_question:
                answer = "Hi! How can I assist you today?"
                ref_list = []  # No references for courtesy words
            else:
                try:
                    output = chain({"question": prompt_question})

                    # Clean the answer by removing unwanted tokens like <pad>, <eos>
                    answer = output['answer'].strip()
                    
                    # Remove <pad> and <eos> if still present
                    answer = ' '.join([word for word in answer.split() if word not in ['<pad>', '<eos>', '<ragbot>']])

                    ref_list = []

                    # Handle source documents for reference links
                    for doc in output['source_documents']:
                        metadata = doc.metadata
                        filename = metadata['source'].split('/')[-1]
                        page_no = metadata['page'] + 1
                        total_pages = metadata['total_pages']
                        ref_list.append({"ref_text": f"{filename} - page {page_no}/{total_pages}",
                                         "ref_link": f"{filename}#page={page_no}"})
                except Exception as e:
                    logging.error(f"Error generating response: {e}")
                    answer = "Sorry, I couldn't process that. Please try again."
                    ref_list = []

            return jsonify({'answer': answer, 'ref_list': ref_list})

        else:  # This handles the regular form submission
            prompt_question = request.form['prompt_question']

            # List of common courtesy words (greetings, thanks, etc.)
            courtesy_words = [
                'hi', 'hello', 'hey', 'hi there', 'hello there', 'hey there',
                'howdy', 'good morning', 'good evening', 'good night',
                'thanks', 'thank you', 'thank you very much', 'thanks a lot',
                'appreciate it', 'many thanks', 'you\'re welcome', 'sorry',
                'excuse me', 'please'
            ]
            
            # If the prompt contains a courtesy word, but not a real question, respond with a greeting
            if any(courtesy_word in prompt_question.lower() for courtesy_word in courtesy_words) and '?' not in prompt_question:
                answer = "Hi! How can I assist you today?"
                ref_list = []  # No references for courtesy words
            else:
                try:
                    output = chain({"question": prompt_question})

                    # Clean the answer by removing unwanted tokens like <pad>, <eos>
                    answer = output['answer'].strip()
                    
                    # Remove <pad> and <eos> if still present
                    answer = ' '.join([word for word in answer.split() if word not in ['<pad>', '<eos>', '<ragbot>']])

                    ref_list = []

                    # Handle source documents for reference links
                    for doc in output['source_documents']:
                        metadata = doc.metadata
                        filename = metadata['source'].split('/')[-1]
                        page_no = metadata['page'] + 1
                        total_pages = metadata['total_pages']
                        ref_list.append({"ref_text": f"{filename} - page {page_no}/{total_pages}",
                                         "ref_link": f"{filename}#page={page_no}"})
                except Exception as e:
                    logging.error(f"Error generating response: {e}")
                    answer = "Sorry, I couldn't process that. Please try again."
                    ref_list = []

            return render_template('home.html', prompt_question=prompt_question, answer=answer, ref_list=ref_list)

    else:
        return render_template('home.html', prompt_question="", answer=None, ref_list=None)


if __name__ == '__main__':
    app.run(debug=True)