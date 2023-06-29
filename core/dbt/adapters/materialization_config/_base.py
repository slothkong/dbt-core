from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Union

import agate

from dbt.contracts.graph.nodes import ModelNode
from dbt.utils import filter_null_values


"""
Relation metadata from the database comes in the form of a collection of one or more `agate.Table`s. In order to
reference the tables, they are added to a dictionary. There can be more than one table because there can be
multiple grains of data for a single object. For example, a materialized view in Postgres has base level information,
like name. But it also can have multiple indexes, which needs to be a separate query. It might look like this:

{
    "materialized_view": agate.Table(
        agate.Row({"table_name": "table_abc", "query": "select * from table_def"})
    ),
    "indexes": agate.Table("rows": [
        agate.Row({"name": "index_a", "columns": ["column_a"], "type": "hash", "unique": False}),
        agate.Row({"name": "index_b", "columns": ["time_dim_a"], "type": "btree", "unique": False}),
    ]),
}

Generally speaking, "primary" `RelationConfig` instances (e.g. materialized view) will be described with
an `agate.Table` and "dependent" `RelationConfig` instances (e.g. index) will be described with an `agate.Row`.
This happens simply because the primary instance is the first step in processing the metadata, but the dependent
instance can be looped when dispatching to it in `parse_describe_relation_results()`.
"""
DescribeRelationResults = Dict[str, Union[agate.Row, agate.Table]]


@dataclass(frozen=True)
class RelationConfig(ABC):
    @classmethod
    def from_dict(cls, kwargs_dict) -> "RelationConfig":
        """
        This assumes the subclass of `RelationConfig` is flat, in the sense that no attribute is
        itself another subclass of `RelationConfig`. If that's not the case, this should be overriden
        to manually manage that complexity. But remember to either call `super().from_dict()` at the end,
        or at least use `filter_null_values()` so that defaults get applied properly for the dataclass.

        Args:
            kwargs_dict: the dict representation of this instance

        Returns: the `RelationConfig` representation associated with the provided dict
        """
        return cls(**filter_null_values(kwargs_dict))  # type: ignore

    @classmethod
    def from_model_node(cls, model_node: ModelNode) -> "RelationConfig":
        """
        A wrapper around `cls.parse_model_node()` and `cls.from_dict()` that pipes the results of the first into
        the second. This shouldn't really need to be overridden; instead, the component methods should be overridden.

        Args:
            model_node: the `model` (`ModelNode`) attribute off of `config` (`RuntimeConfigObject`) in the global
                jinja context of a materialization

        Returns:
            a validated `RelationConfig` instance specific to the adapter and relation type
        """
        relation_config = cls.parse_model_node(model_node)
        relation = cls.from_dict(relation_config)
        return relation

    @classmethod
    @abstractmethod
    def parse_model_node(cls, model_node: ModelNode) -> dict:
        """
        The purpose of this method is to translate the dbt/user generic parlance into the database parlance and
        format it for `RelationConfig` consumption.

        In many cases this may be a one-to-one mapping; e.g. dbt calls it "schema_name" and the database calls it
        "schema_name". This could also be a renaming, calculation, or dispatch to a lower grain object.

        See `dbt/adapters/postgres/relation_configs/materialized_view.py` to see an example implementation.

        Args:
            model_node: the `model` (`ModelNode`) attribute off of `config` (`RuntimeConfigObject`) in the global
                jinja context of a materialization

        Returns:
            a non-validated dictionary version of a `RelationConfig` instance specific to the adapter and
            relation type
        """
        raise NotImplementedError(
            "`parse_model_node()` needs to be implemented for this relation."
        )

    @classmethod
    def from_describe_relation_results(
        cls, describe_relation_results: DescribeRelationResults
    ) -> "RelationConfig":
        """
        A wrapper around `cls.parse_describe_relation_results()` and `cls.from_dict()` that pipes the results of the
        first into the second. This shouldn't really need to be overridden; instead, the component methods should
        be overridden.

        Args:
            describe_relation_results: the results of one or more queries run against the database to gather the
                requisite metadata to describe this relation

        Returns:
            a validated `RelationConfig` instance specific to the adapter and relation type
        """
        relation_config = cls.parse_describe_relation_results(describe_relation_results)
        relation = cls.from_dict(relation_config)
        return relation

    @classmethod
    @abstractmethod
    def parse_describe_relation_results(
        cls, describe_relation_results: DescribeRelationResults
    ) -> dict:
        """
        The purpose of this method is to format the database parlance for `RelationConfig` consumption.

        This tends to be one-to-one except for combining grains of data. For example, a single materialized
        view could have multiple indexes which would result in multiple queries to the database to build one
        materialized view config object. All of these pieces get knit together here.

        See `dbt/adapters/postgres/relation_configs/materialized_view.py` to see an example implementation.

        Args:
            describe_relation_results: the results of one or more queries run against the database to gather the
                requisite metadata to describe this relation

        Returns:
            a non-validated dictionary version of a `RelationConfig` instance specific to the adapter and
            relation type
        """
        raise NotImplementedError(
            "`parse_describe_relation_results()` needs to be implemented for this relation."
        )