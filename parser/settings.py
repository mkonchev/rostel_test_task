import os
from dotenv import load_dotenv

load_dotenv()


class Settings():
    URL: str = os.getenv("URL", "https://www.rialcom.ru/internet_tariffs/")


settings = Settings()
