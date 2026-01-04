@echo off
setlocal
set OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxx
streamlit run app.py --server.port 8501 --server.address localhost
pause


