import os
import sys
from pathlib import Path
from django.core.asgi import get_asgi_application

base_dir = Path(__file__).resolve().parent.parent
talentvault_dir = base_dir.parent / '2020Tech'
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))
if talentvault_dir.exists() and str(talentvault_dir) not in sys.path:
    sys.path.insert(1, str(talentvault_dir))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
