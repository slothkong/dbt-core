from dataclasses import dataclass
from typing import Any, Dict, Optional

from dbt.contracts.graph.nodes import ParsedNode
from dbt.contracts.relation import ComponentName

from dbt.adapters.relation.models._relation_component import (
    DescribeRelationResults,
    RelationComponent,
)


@dataclass(frozen=True)
class DatabaseRelation(RelationComponent):
    """
    This config identifies the minimal materialization parameters required for dbt to function as well
    as built-ins that make macros more extensible. Additional parameters may be added by subclassing for your adapter.
    """

    name: str

    def __str__(self) -> str:
        return self.fully_qualified_path or ""

    @property
    def fully_qualified_path(self) -> Optional[str]:
        return self.render.part(ComponentName.Database, self.name)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "DatabaseRelation":
        """
        Parse `config_dict` into a `DatabaseRelation` instance, applying defaults
        """
        database = super().from_dict(config_dict)
        assert isinstance(database, DatabaseRelation)
        return database

    @classmethod
    def parse_node(cls, node: ParsedNode) -> Dict[str, Any]:
        """
        Parse `ModelNode` into a dict representation of a `DatabaseRelation` instance

        This is generally used indirectly by calling `from_model_node()`, but there are times when the dict
        version is more useful

        Args:
            node: the `model` attribute in the global jinja context

        Example `model_node`:

        ModelNode({
            "database": "my_database",
            ...,
        })

        Returns: a `DatabaseRelation` instance as a dict, can be passed into `from_dict`
        """
        return {"name": node.database}

    @classmethod
    def parse_describe_relation_results(
        cls, describe_relation_results: DescribeRelationResults
    ) -> Dict[str, Any]:
        """
        Parse database metadata into a dict representation of a `DatabaseRelation` instance

        This is generally used indirectly by calling `from_describe_relation_results()`,
        but there are times when the dict version is more appropriate.

        Args:
            describe_relation_results: the results of a set of queries that fully describe an instance of this class

        Example of `describe_relation_results`:

        agate.Row({
            "database_name": "my_database",
        })

        Returns: a `DatabaseRelation` instance as a dict, can be passed into `from_dict`
        """
        relation = cls._parse_single_record_from_describe_relation_results(
            describe_relation_results, "relation"
        )
        return {"name": relation["database_name"]}