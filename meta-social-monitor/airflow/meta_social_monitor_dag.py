"""Alternative scheduler: Airflow DAG (use this OR the GitHub Action, not both).

Each name in ENV_VARS is read from the worker's environment first, then from an Airflow
Variable of the same name. The Salesforce push never blocks the Slack report.
"""
from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

local_tz = pendulum.timezone("America/Chicago")

ENV_VARS = [
    "META_ACCESS_TOKEN", "META_PAGE_ID", "META_IG_USER_ID",
    "SLACK_WEBHOOK_URL", "ANTHROPIC_API_KEY",
    "SF_DOMAIN", "SF_CLIENT_ID", "SF_CLIENT_SECRET",
]


def run_monitor(**context):
    import os
    from airflow.models import Variable

    for name in ENV_VARS:
        if not os.environ.get(name):
            value = Variable.get(name, default_var=None)
            if value:
                os.environ[name] = value

    from monitor.main import main
    main([])


with DAG(
    dag_id="meta_social_monitor",
    schedule="30 7 * * *",
    start_date=datetime(2026, 10, 21, tzinfo=local_tz),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=20)},
    tags=["meta", "social", "monitoring"],
) as dag:
    PythonOperator(task_id="run_monitor", python_callable=run_monitor)
