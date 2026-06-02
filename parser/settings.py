import os
from dotenv import load_dotenv

load_dotenv()


class Settings():
    URL: str = os.getenv("URL", "https://www.rialcom.ru/internet_tariffs/")
    ACCEPT: str = os.getenv("ACCEPT", "text/html")
    USER_AGENT: str = os.getenv(
        "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": self.ACCEPT,
            "User-Agent": self.USER_AGENT,
        }


settings = Settings()
