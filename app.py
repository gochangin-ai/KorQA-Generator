import json
from dotenv import load_dotenv

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chains import SequentialChain
import streamlit as st
import traceback
import pandas as pd
from langchain.callbacks import get_openai_callback
from utils import parse_file, get_table_data, RESPONSE_JSON,RESPONSE_JSON_TF,RESPONSE_JSON_ShortAnswer

load_dotenv()

# This is an LLMChain to create 10-20 multiple choice questions from a given piece of text.
llm =ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

template = """
Text: {text}
You are an expert {QA_type} maker. Given the above text, it is your job to\
create a quiz of {number} multiple choice questions for grade {grade} students in {tone} tone.
Make sure that questions are not repeated and check all the questions to be conforming to the text as well.
It must be written in Korean.\
Make sure to format your response like the RESPONSE_JSON below and use it as a guide.\
Ensure to make the {number} {QA_type}s.
### RESPONSE_JSON
{response_json}
"""
quiz_generation_prompt = PromptTemplate(
    input_variables=["QA_type","text", "number", "grade", "tone", "response_json"],
    template=template,
)
quiz_chain = LLMChain(
    llm=llm, prompt=quiz_generation_prompt, output_key="quiz", verbose=True
)

# This is an LLMChain to evaluate the multiple choice questions created by the above chain
llm =ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
template = """You are an human resources expert and writer. Given a {QA_type} quiz for {grade} grade students.\
You need to evaluate complexity of the questions and give a complete analysis of the quiz if the students 
will be able to understand the questions and answer them. Only use at max 50 words for complexity analysis.
If quiz is not at par with the cognitive and analytical abilities of the students,
It must be written in Korean.\
update the quiz questions which need to be changed and change the tone such that it perfectly fits the students abilities.
It must be written in Korean.\
Quiz {QA_type}s:
{quiz}
Critique from an expert english writer of the above quiz:"""

quiz_evaluation_prompt = PromptTemplate(
    input_variables=["QA_type","grade", "quiz"], template=template
)
review_chain = LLMChain(
    llm=llm, prompt=quiz_evaluation_prompt, output_key="review", verbose=True
)

# This is the overall chain where we run these two chains in sequence.
generate_evaluate_chain = SequentialChain(
    chains=[quiz_chain, review_chain],
    input_variables=["QA_type","text", "number", "grade", "tone", "response_json"],
    # Here we return multiple variables
    output_variables=["quiz", "review"],
    verbose=True,
)

st.title("문서 이해 바탕 문제 생성")

# Create a form using st.form
with st.form("user_inputs"):
    # File upload
    uploaded_file = st.file_uploader("Upload a pdf or text file")

    # Input fields
    QA_type = ['TF', 'MCQ', 'ShortAnswer']
    selected_QA_type = st.selectbox('문제 유형', QA_type)
    mcq_count = st.number_input("문제 수", min_value=3, max_value=20)
    grade = st.number_input("문제 수준 (1-10)", min_value=1, max_value=10)
    tone = st.text_input("퀴즈 분위기 (simple, funny, etc.)", max_chars=100, placeholder="simple")

    button = st.form_submit_button("Create quiz")

# Check if the button is clicked and all fields have inputs
if selected_QA_type and button and uploaded_file is not None and mcq_count and grade and tone:
    with st.spinner("Loading..."):
        try:
            text = parse_file(uploaded_file)

            # count tokens and cost of api call
            if selected_QA_type=="MCQ":
                with get_openai_callback() as cb:
                    response = generate_evaluate_chain(
                        {
                            "QA_type":selected_QA_type,
                            "text": text,
                            "number": mcq_count,
                            "grade": grade,
                            "tone": tone,
                            "response_json": json.dumps(RESPONSE_JSON),
                        }
                    )
            elif selected_QA_type=="TF":
                with get_openai_callback() as cb:
                    response = generate_evaluate_chain(
                        {
                            "QA_type":selected_QA_type,
                            "text": text,
                            "number": mcq_count,
                            "grade": grade,
                            "tone": tone,
                            "response_json": json.dumps(RESPONSE_JSON_TF),
                        }
                    )
            elif selected_QA_type=="ShortAnswer":
                with get_openai_callback() as cb:
                    response = generate_evaluate_chain(
                        {
                            "QA_type":selected_QA_type,
                            "text": text,
                            "number": mcq_count,
                            "grade": grade,
                            "tone": tone,
                            "response_json": json.dumps(RESPONSE_JSON_ShortAnswer),
                        }
                    )
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            st.error("Error")
        else:
            print(f"Total Tokens: {cb.total_tokens}")
            print(f"Prompt Tokens: {cb.prompt_tokens}")
            print(f"Completion Tokens: {cb.completion_tokens}")
            print(f"Total Cost (USD): ${cb.total_cost}")

            if isinstance(response, dict):
                # Extract quiz data from the response
                quiz = response.get("quiz", None)
                if quiz is not None:
                    table_data = get_table_data(quiz)
                    if table_data is not None:
                        df = pd.DataFrame(table_data)
                        df.index = df.index + 1
                        st.table(df)
                        # Display the review in a text box
                        st.text_area(label="Review", value=response["review"])
                    else:
                        st.error("Error in table data")
            else:
                st.write(response)