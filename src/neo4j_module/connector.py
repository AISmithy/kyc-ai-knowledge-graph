"""Neo4j database connection test and utilities."""

import os
from typing import Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable, AuthError

# Load environment variables from .env file
load_dotenv()


class Neo4jConnection:
    """Manages Neo4j database connection and basic operations."""

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        database: str = None,
    ):
        """Initialize Neo4j connection.

        Args:
            uri: Neo4j server URI (defaults to NEO4J_URI env var)
            username: Database username (defaults to NEO4J_USERNAME env var)
            password: Database password (defaults to NEO4J_PASSWORD env var)
            database: Database name (defaults to NEO4J_DATABASE env var)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver: Optional[Driver] = None

    def connect(self) -> bool:
        """Establish connection to Neo4j database.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # neo4j+s and neo4j+ssc schemes already include encryption
            # Don't set encrypted param for neo4j+s, bolt+s, etc
            driver_kwargs = {
                "auth": (self.username, self.password),
            }
            if self.uri.startswith("bolt://") or self.uri.startswith("neo4j://"):
                driver_kwargs["encrypted"] = False
            
            self.driver = GraphDatabase.driver(self.uri, **driver_kwargs)
            
            # Verify connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            print(f"✓ Connected to Neo4j at {self.uri}")
            return True
        except (ServiceUnavailable, AuthError) as e:
            print(f"✗ Connection failed: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False

    def close(self) -> None:
        """Close database connection."""
        if self.driver:
            self.driver.close()
            print("✓ Connection closed")

    def get_session(self) -> Optional[Session]:
        """Get an active session.

        Returns:
            Neo4j session or None if not connected
        """
        if not self.driver:
            print("✗ Not connected. Call connect() first.")
            return None
        return self.driver.session(database=self.database)

    def test_query(self) -> bool:
        """Run a simple test query.

        Returns:
            True if query executed successfully
        """
        session = self.get_session()
        if not session:
            return False

        try:
            result = session.run("RETURN 'Neo4j is working!' as message")
            for record in result:
                print(f"✓ Query result: {record['message']}")
            session.close()
            return True
        except Exception as e:
            print(f"✗ Query failed: {e}")
            session.close()
            return False

    def get_database_info(self) -> Optional[dict]:
        """Retrieve database information.

        Returns:
            Dictionary with database info or None if error
        """
        session = self.get_session()
        if not session:
            return None

        try:
            result = session.run("CALL dbms.components()")
            info = {}
            for record in result:
                info = dict(record)
            session.close()
            return info
        except Exception as e:
            print(f"✗ Failed to get database info: {e}")
            session.close()
            return None


def test_neo4j_connection(
    uri: str = None,
    username: str = None,
    password: str = None,
    database: str = None,
) -> None:
    """Test Neo4j connection with credentials from env or parameters.

    Args:
        uri: Neo4j server URI (uses NEO4J_URI env var if not provided)
        username: Database username (uses NEO4J_USERNAME env var if not provided)
        password: Database password (uses NEO4J_PASSWORD env var if not provided)
        database: Database name (uses NEO4J_DATABASE env var if not provided)
    """
    print("\n" + "=" * 60)
    print("Neo4j Connection Test")
    print("=" * 60)

    conn = Neo4jConnection(uri=uri, username=username, password=password, database=database)

    print(f"URI: {conn.uri}")
    print(f"User: {conn.username}")
    print(f"Database: {conn.database}\n")

    # Test connection
    if not conn.connect():
        print("Cannot proceed without connection.\n")
        return

    # Run test query
    conn.test_query()

    # Get database info
    print("\nDatabase Info:")
    info = conn.get_database_info()
    if info:
        for key, value in info.items():
            print(f"  {key}: {value}")
    else:
        print("  (unable to retrieve)")

    # Close connection
    conn.close()
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    # Run test using credentials from .env file
    test_neo4j_connection()
