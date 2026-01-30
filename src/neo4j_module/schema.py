"""Neo4j graph schema setup and utilities."""

from typing import Optional

from neo4j_module.connector import Neo4jConnection


class GraphSchemaManager:
    """Manages Neo4j graph schema creation, constraints, and indices."""

    def __init__(self, connection: Neo4jConnection):
        """Initialize schema manager with a Neo4j connection.

        Args:
            connection: Neo4jConnection instance
        """
        self.connection = connection

    def create_constraints(self) -> bool:
        """Create all unique constraints for the graph schema.

        Returns:
            True if all constraints created successfully
        """
        constraints = [
            "CREATE CONSTRAINT lei_unique IF NOT EXISTS FOR (e:LegalEntity) REQUIRE e.lei IS UNIQUE",
            "CREATE CONSTRAINT address_id_unique IF NOT EXISTS FOR (a:Address) REQUIRE a.addressId IS UNIQUE",
            "CREATE CONSTRAINT authority_id_unique IF NOT EXISTS FOR (ra:RegistrationAuthority) REQUIRE ra.authorityId IS UNIQUE",
            "CREATE CONSTRAINT lou_id_unique IF NOT EXISTS FOR (l:ManagingLOU) REQUIRE l.louId IS UNIQUE",
            "CREATE CONSTRAINT rel_type_unique IF NOT EXISTS FOR (rt:RelationshipType) REQUIRE rt.relationshipTypeCode IS UNIQUE",
        ]

        session = self.connection.get_session()
        if not session:
            return False

        try:
            for constraint in constraints:
                session.run(constraint)
                print(f"✓ Created constraint: {constraint.split('FOR')[0].strip()}")
            session.close()
            return True
        except Exception as e:
            print(f"✗ Failed to create constraints: {e}")
            session.close()
            return False

    def create_indices(self) -> bool:
        """Create all indices for performance optimization.

        Returns:
            True if all indices created successfully
        """
        indices = [
            "CREATE INDEX lei_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.lei)",
            "CREATE INDEX legal_name_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.legalName)",
            "CREATE INDEX entity_status_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.entityStatus)",
            "CREATE INDEX country_index IF NOT EXISTS FOR (a:Address) ON (a.country)",
            "CREATE INDEX city_index IF NOT EXISTS FOR (a:Address) ON (a.city)",
            "CREATE INDEX authority_country_index IF NOT EXISTS FOR (ra:RegistrationAuthority) ON (ra.country)",
            "CREATE INDEX jurisdiction_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.legalJurisdiction)",
        ]

        session = self.connection.get_session()
        if not session:
            return False

        try:
            for index in indices:
                session.run(index)
                print(f"✓ Created index: {index.split('FOR')[0].strip()}")
            session.close()
            return True
        except Exception as e:
            print(f"✗ Failed to create indices: {e}")
            session.close()
            return False

    def initialize_schema(self) -> bool:
        """Initialize the complete graph schema (constraints + indices).

        Returns:
            True if schema initialization successful
        """
        print("\n" + "=" * 60)
        print("Initializing Graph Schema")
        print("=" * 60)

        if not self.create_constraints():
            print("Failed to create constraints.")
            return False

        print()

        if not self.create_indices():
            print("Failed to create indices.")
            return False

        print("\n" + "=" * 60)
        print("Schema Initialization Complete")
        print("=" * 60 + "\n")
        return True

    def get_schema_info(self) -> Optional[dict]:
        """Retrieve current schema information from database.

        Returns:
            Dictionary with constraints, indices, and node labels
        """
        session = self.connection.get_session()
        if not session:
            return None

        try:
            # Get constraints
            constraints_result = session.run("SHOW CONSTRAINTS")
            constraints = [dict(record) for record in constraints_result]

            # Get indices (try both SHOW INDICES and SHOW INDEX)
            try:
                indices_result = session.run("SHOW INDEXES")
                indices = [dict(record) for record in indices_result]
            except:
                indices_result = session.run("SHOW INDEX")
                indices = [dict(record) for record in indices_result]

            # Get node labels
            labels_result = session.run("CALL db.labels()")
            labels = [record["label"] for record in labels_result]

            session.close()

            return {
                "constraints": constraints,
                "indices": indices,
                "labels": labels,
            }
        except Exception as e:
            print(f"✗ Failed to retrieve schema info: {e}")
            session.close()
            return None

    def print_schema_info(self) -> None:
        """Print current schema information in a readable format."""
        info = self.get_schema_info()
        if not info:
            print("Could not retrieve schema info.")
            return

        print("\n" + "=" * 60)
        print("Current Graph Schema")
        print("=" * 60)

        print("\nNode Labels:")
        for label in info["labels"]:
            print(f"  - {label}")

        print("\nConstraints:")
        if info["constraints"]:
            for constraint in info["constraints"]:
                print(f"  - {constraint.get('name', 'Unknown')}: {constraint.get('description', '')}")
        else:
            print("  (none)")

        print("\nIndices:")
        if info["indices"]:
            for index in info["indices"]:
                print(f"  - {index.get('name', 'Unknown')}: {index.get('description', '')}")
        else:
            print("  (none)")

        print("\n" + "=" * 60 + "\n")


def setup_graph_schema() -> None:
    """Initialize graph schema in Neo4j database."""
    from neo4j_module.connector import Neo4jConnection

    conn = Neo4jConnection()
    if not conn.connect():
        print("Cannot proceed without connection.")
        return

    schema_manager = GraphSchemaManager(conn)
    schema_manager.initialize_schema()
    schema_manager.print_schema_info()

    conn.close()


if __name__ == "__main__":
    setup_graph_schema()
