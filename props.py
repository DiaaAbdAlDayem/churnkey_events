from enum import Enum
from os import environ


class Key(Enum):
    DATABASE_NAME = 1
    QUERY_RESULTS_S3_BUCKET = 2
    QUERY_RESULTS_S3_LOCATION = 3
    SECRET_NAME = 4


def get(key: Key):
    if "PROFILE" in environ:
        profile = environ["PROFILE"]
    else:
        profile = "dev"

    return {
        "dev": {
            Key.DATABASE_NAME: "dev-warehouse",
            key.QUERY_RESULTS_S3_BUCKET: "dev-quizplus-query-results",
            Key.QUERY_RESULTS_S3_LOCATION: "s3://dev-quizplus-query-results/reporting/",
            Key.SECRET_NAME: "dev/churnkey",
        },
        "prod": {
            Key.DATABASE_NAME: "prod-warehouse",
            key.QUERY_RESULTS_S3_BUCKET: "prod-quizplus-query-results",
            Key.QUERY_RESULTS_S3_LOCATION: "s3://prod-quizplus-query-results/reporting/",
            Key.SECRET_NAME: "prod/churnkey",
        },
    }[profile][key]
