from fastapi import FastAPI

app = FastAPI(title='ATS Recruitment API', version='0.1.0')


@app.get('/')
def read_root() -> dict[str, str]:
    return {'message': 'ATS Recruitment API is running'}


@app.get('/health')
def healthcheck() -> dict[str, str]:
    return {'status': 'ok'}
