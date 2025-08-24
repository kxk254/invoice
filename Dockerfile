FROM python:3.10-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Optional but Recommended: Set a UTF-8 locale
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

WORKDIR /invoice

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Core build essentials
    build-essential \
    libffi-dev \
    zlib1g-dev 
    # WeasyPrint core rendering dependencies
RUN apt-get install -y --no-install-recommends libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0
RUN apt-get install -y --no-install-recommends  libgdk-pixbuf2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libharfbuzz0b
    # Image format support (crucial for JPG/PNG)
RUN apt-get install -y --no-install-recommends libjpeg62-turbo libpng16-16
# RUN apt-get install -y --no-install-recommends libsvg1
    # X11 related (sometimes needed for fontconfig, safer to include)
RUN apt-get install -y --no-install-recommends libxrender1 
RUN apt-get install -y --no-install-recommends libxi6 
RUN apt-get install -y --no-install-recommends libxrandr2 
    # Font utilities and recommended fonts
RUN apt-get install -y --no-install-recommends fontconfig 
RUN apt-get install -y --no-install-recommends fonts-monapo
# RUN apt-get install -y --no-install-recommends fonts-arphic-uming
# RUN apt-get install -y --no-install-recommends fonts-takao
# RUN apt-get install -y --no-install-recommends fonts-vl-gothic 
# RUN apt-get install -y --no-install-recommends fonts-freefont-ttf && 
# RUN apt-get install -y --no-install-recommends fonts-noto-cjk

# RUN apt-get install -y --no-install-recommends fonts-ipafont \
    # Update font cache (important for WeasyPrint to find fonts)
# RUN apt-get install -y --no-install-recommends fc-cache -f -v && \
RUN apt-get clean
    # Clean up apt cache to reduce image size
RUN rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir weasyprint

COPY .  .

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]