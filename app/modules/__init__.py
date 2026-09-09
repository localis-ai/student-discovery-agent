"""Init module
Load routes in all modules
"""

import importlib
import os
import pkgutil

from fastapi import APIRouter

from app.modules.common.utils.logging import logger

route = APIRouter(prefix="/api")
package = "app.modules"

# Duyệt qua từng module trong `modules` (ví dụ: users, products, ...)
for finder, module_name, ispkg in pkgutil.iter_modules([package.replace(".", "/")]):
    logger.info(f"Loading module: {module_name}, is package: {ispkg}, finder: {finder}")
    module_path = f"{package}.{module_name}.routes"

    try:
        # Lấy danh sách thư mục trong `routes/`
        routes_dir = f"{module_path.replace('.', '/')}"
        version_folders = [d for d in os.listdir(routes_dir) if os.path.isdir(f"{routes_dir}/{d}") and d.startswith("v")]
        for version_name in version_folders:
            version_path = f"{module_path}.{version_name}"

            # Duyệt tất cả file trong v1, v2 (vd: user_route.py, authen_route.py)
            for _, route_name, _ in pkgutil.iter_modules([f"{version_path.replace('.', '/')}"]):
                route_module_path = f"{version_path}.{route_name}"
                try:
                    module = importlib.import_module(route_module_path)

                    if hasattr(module, "router"):
                        # Lấy tên route (bỏ `_route` nếu có)
                        logger.info(f"/{version_name}{module.router.prefix}")
                        route.include_router(module.router, prefix=f"/{version_name}")
                        logger.info(f"✅ Loaded {route_module_path}")

                except ModuleNotFoundError as e:
                    logger.info(f"⚠️ Module {route_module_path} not found: {e}")
                    pass

    except FileNotFoundError as e:
        logger.info(f"⚠️ Folder {module_path} not found: {e}")
        pass


# for finder, name, ispkg in pkgutil.iter_modules([package.replace(".", "/")]):
#     try:
#         module = importlib.import_module(f"{package}.{name}.routes.index")

#         if hasattr(module, "route"):
#             route.include_router(module.route)
#     except ModuleNotFoundError as e:
#         logger.info(e)
#         pass
