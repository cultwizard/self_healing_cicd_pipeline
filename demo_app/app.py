from fastapi import FastAPI

app = FastAPI(title="Demo Target Microservice")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/calculate")
def calculate(a: int, b: int):
    return {"result": a / b}
