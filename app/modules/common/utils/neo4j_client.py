from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.core.config import settings
from app.modules.common.utils.logging import logger


@lru_cache(maxsize=1)
def get_neo4j_driver() -> Driver:
    """Trả về Neo4j driver dùng chung (singleton)."""
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    return driver


def neo4j_health_check() -> bool:
    """Kiểm tra kết nối Neo4j."""
    try:
        get_neo4j_driver().verify_connectivity()
        return True
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        return False


@lru_cache(maxsize=1)
def get_graphiti():
    """Trả về Graphiti client dùng chung (semantic + graph trên Neo4j).

    NOTE: Graphiti (graphiti-core==0.3.0) API/constructor signature is used
    per the task spec and has not been verified against a live install in
    this scaffold-only pass.
    """
    from graphiti_core import Graphiti

    return Graphiti(
        settings.NEO4J_URI,
        settings.NEO4J_USER,
        settings.NEO4J_PASSWORD,
    )
