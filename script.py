#!/usr/bin/env python

import boto3
import pandas as pd
import props
import time
import json
import requests
from dtypes import unlocks_dtypes, view_dtypes
import numpy as np
import math

props.get(props.Key.DATABASE_NAME)

athena = boto3.client("athena")
s3 = boto3.client("s3")
DATABASE_NAME = props.get(props.Key.DATABASE_NAME)
SECRET_NAME = props.get(props.Key.SECRET_NAME)

QUERY_RESULTS_S3_BUCKET = props.get(props.Key.QUERY_RESULTS_S3_BUCKET)
QUERY_RESULTS_S3_LOCATION = props.get(props.Key.QUERY_RESULTS_S3_LOCATION)

session = boto3.session.Session()
secretsmanager_client = session.client('secretsmanager')

# Retrieve the value of the secret of DB connection
# secret_dict = secretsmanager_client.get_secret_value(SecretId=DB_SECRET_NAME)
secret_dict = secretsmanager_client.get_secret_value(SecretId=SECRET_NAME)
churnkey_secret = json.loads(secret_dict['SecretString'])


def execute_athena_query(query, table):
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": f"{DATABASE_NAME}"},
        ResultConfiguration={"OutputLocation": QUERY_RESULTS_S3_LOCATION + f'{table}'},
    )

    query_execution_id = response["QueryExecutionId"]
    # Wait for the query result
    done = False
    while not done:
        status_response = athena.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status = status_response["QueryExecution"]["Status"]["State"]
        print(f"Query status: {status}")
        if status == "QUEUED" or status == "RUNNING":
            time.sleep(1)
        elif status == "FAILED":
            error_message = status_response["QueryExecution"]["Status"][
                "StateChangeReason"
            ]
            print("Query failed: {}".format(error_message))
            raise Exception("Query status is FAILED")
        else:
            done = True
    query_execution_id += '.csv'
    print(f"query_execution_id = {query_execution_id}")

    # print(query)
    res = s3.get_object(Bucket=QUERY_RESULTS_S3_BUCKET, Key=f'reporting/{table}/' + query_execution_id)
    df = pd.read_csv(res['Body'])

    return df


views_query = f"""
SELECT 
    IF(weight = 10, 'Answer Viewed', 'Question Viewed') AS event,
    te.user_id AS uid,
    customer_id AS customerId,
    created_at AS eventDate
FROM "{DATABASE_NAME}"."tracking-events" te
    INNER JOIN ( SELECT DISTINCT user_id, customer_id FROM "{DATABASE_NAME}"."subscription" WHERE gateway = 'STRIPE' ) s 
        ON te.user_id = s.user_id
WHERE te.action <> 'SEARCH' AND te.question_id IS NOT NULL
  AND te.created_at > DATE('2023-12-13') 
  AND te.created_at < DATE('2023-12-30')
ORDER BY te.created_at;
"""

views_df = execute_athena_query(views_query, 'view_events')
views_df = views_df.astype({x: view_dtypes[x] for x in views_df.columns})
views_df['eventDate'] = pd.to_datetime(views_df['eventDate'])

print(f"len = {len(views_df)}")

views_agg = views_df
df = views_df.sort_values(by=["eventDate"], ascending=True).reset_index(drop=True)
df = df.astype({"eventDate": str})


headers = {
    "x-ck-api-key": churnkey_secret["secret"],
    "x-ck-app": churnkey_secret["ck_app_id"],
}

chunks = np.array_split(df, math.ceil(len(df) / 100))
for ind, chunk in enumerate(chunks):
    print(ind)
    event_body = chunk.to_dict('records')
    response = requests.post("https://api.churnkey.co/v1/api/events/bulk", json=event_body, headers=headers)
    print(response.status_code)
    print(response.json())