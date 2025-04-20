import boto3
import json


def create_cluster(client, config_path: str) -> str:
    config = json.loads(open(config_path, "r").read())
    res = client.run_job_flow(**config)
    return res["JobFlowId"]


if __name__ == "__main__":
    # Create an EMR client
    emr = boto3.client("emr")
    
    # Create the cluster
    cluster_id = create_cluster(emr, "./config.json")
    
    print(f"Created cluster: {cluster_id}")