from collections import namedtuple
from typing import Dict

import pytest

from dbt.contracts.results import TestStatus
from dbt.tests.util import run_dbt, check_relation_types

from dbt.tests.adapter.store_test_failures_tests._files import (
    SEED__CHIPMUNKS,
    MODEL__CHIPMUNKS,
    TEST__FAIL_AS_VIEW,
    TEST__PASS_AS_VIEW,
    TEST__FAIL_AS_TABLE,
    TEST__PASS_AS_TABLE,
)


class StoreTestFailures:
    seed_table: str = "chipmunks_stage"
    model_table: str = "chipmunks"
    audit_schema_suffix: str = "dbt_test__audit"

    audit_schema: str

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(self, project):
        # the seed doesn't get touched, load it once
        run_dbt(["seed"])
        yield

    @pytest.fixture(scope="function", autouse=True)
    def setup_method(self, project, setup_class):
        # make sure the model is always right
        run_dbt(["run"])

        # the name of the audit schema doesn't change in a class, but this doesn't run at the class level
        self.audit_schema = f"{project.test_schema}_{self.audit_schema_suffix}"
        yield

    @pytest.fixture(scope="function", autouse=True)
    def teardown_method(self, project):
        yield

        # clear out the audit schema after each test case
        with project.adapter.connection_named("__test"):
            audit_schema = project.adapter.Relation.create(
                database=project.database, schema=self.audit_schema
            )
            project.adapter.drop_schema(audit_schema)

    @pytest.fixture(scope="class")
    def seeds(self):
        return {f"{self.seed_table}.csv": SEED__CHIPMUNKS}

    @pytest.fixture(scope="class")
    def models(self):
        return {f"{self.model_table}.sql": MODEL__CHIPMUNKS}

    @pytest.fixture(scope="class")
    def tests(self):
        return {
            "fail_as_view.sql": TEST__FAIL_AS_VIEW,
            "pass_as_view.sql": TEST__PASS_AS_VIEW,
            "fail_as_table.sql": TEST__FAIL_AS_TABLE,
            "pass_as_table.sql": TEST__PASS_AS_TABLE,
        }

    def row_count(self, project, relation_name: str) -> int:
        """
        Return the row count for the relation.

        Args:
            project: the project fixture
            relation_name: the name of the relation

        Returns:
            the row count as an integer
        """
        sql = f"select count(*) from {self.audit_schema}.{relation_name}"
        return project.run_sql(sql, fetch="one")[0]

    def insert_record(self, project, record: Dict[str, str]):
        field_names, field_values = [], []
        for field_name, field_value in record.items():
            field_names.append(field_name)
            field_values.append(f"'{field_value}'")
        field_name_clause = ", ".join(field_names)
        field_value_clause = ", ".join(field_values)

        sql = f"""
        insert into {project.test_schema}.{self.model_table} ({field_name_clause})
        values ({field_value_clause})
        """
        project.run_sql(sql)

    def delete_record(self, project, record: Dict[str, str]):
        where_clause = " and ".join(
            [f"{field_name} = '{field_value}'" for field_name, field_value in record.items()]
        )
        sql = f"""
        delete from {project.test_schema}.{self.model_table}
        where {where_clause}
        """
        project.run_sql(sql)

    def test_tests_run_successfully_and_are_stored_as_expected(self, project):
        # set up the expected results
        TestResult = namedtuple("TestResult", ["name", "status", "type", "row_count"])
        expected_results = {
            TestResult("pass_as_view", TestStatus.Pass, "view", 0),
            TestResult("fail_as_view", TestStatus.Fail, "view", 1),
            TestResult("pass_as_table", TestStatus.Pass, "table", 0),
            TestResult("fail_as_table", TestStatus.Fail, "table", 1),
        }

        # run the tests once
        results = run_dbt(["test", "--store-failures"], expect_pass=False)

        # show that the statuses are what we expect
        actual = {(result.node.name, result.status) for result in results}
        expected = {(result.name, result.status) for result in expected_results}
        assert actual == expected

        # show that the results are persisted in the correct database objects
        check_relation_types(
            project.adapter, {result.name: result.type for result in expected_results}
        )

        # show that only the failed records show up
        actual = {
            (result.name, self.row_count(project, result.name)) for result in expected_results
        }
        expected = {(result.name, result.row_count) for result in expected_results}
        assert actual == expected

        # insert a new record in the model that fails the "pass" tests
        # show that the view updates, but not the table
        self.insert_record(project, {"name": "dave", "shirt": "grape"})
        expected_results.remove(TestResult("pass_as_view", TestStatus.Pass, "view", 0))
        expected_results.add(TestResult("pass_as_view", TestStatus.Pass, "view", 1))

        # delete the original record from the model that failed the "fail" tests
        # show that the view updates, but not the table
        self.delete_record(project, {"name": "theodore", "shirt": "green"})
        expected_results.remove(TestResult("fail_as_view", TestStatus.Fail, "view", 1))
        expected_results.add(TestResult("fail_as_view", TestStatus.Fail, "view", 0))

        # show that the views update without needing to run dbt, but the tables do not update
        actual = {
            (result.name, self.row_count(project, result.name)) for result in expected_results
        }
        expected = {(result.name, result.row_count) for result in expected_results}
        assert actual == expected