# base image
FROM python:3.10-slim

# set the work dir 
WORKDIR /app

# copy code into the workdir
COPY . /app

# install poetry
RUN pip install poetry

# install dependencies
RUN poetry install --no-dev

# expose port 8000
EXPOSE 8000

# run the server
CMD ["poetry", "run", "uvicorn", "book_api.main:app", "--host", "0.0.0.0", "--port", "8000"]