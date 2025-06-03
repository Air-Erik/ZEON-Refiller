# app/__main__.py

import asyncio
from .vm_refiller_service import main

if __name__ == "__main__":
    asyncio.run(main())
