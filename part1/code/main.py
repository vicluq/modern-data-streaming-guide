from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import year, month, day, col, map_from_entries
from pyspark.sql.types import StringType
import os

# Retrieve Environment
topics = os.environ['ConsumerTopics']
brokers = os.environ['MskBrokers']
bucket = os.environ['Bucket']

# Initialize Spark Session
spark = SparkSession.builder \
    .appName("KafkaStreamingConsumer") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,software.amazon.msk:aws-msk-iam-auth:2.3.1") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .getOrCreate()


# Process batches
def process(batch_df: DataFrame, batch_id):
  batch_df = (
      batch_df
        # Create date columns to allow partitioning
        .withColumn("year", year(col("timestamp").cast("timestamp")))
        .withColumn("month", month(col("timestamp").cast("timestamp")))
        .withColumn("day", day(col("timestamp").cast("timestamp")))
        # Handle Headers
        .withColumn("headers", map_from_entries(col("headers")))
        .withColumn("trace", col("headers.trace-id").cast(StringType()))
        .withColumn("value", col("value").cast(StringType()))
  )

  batch_df.write \
    .partitionBy("year", "month", "day") \
    .mode("append") \
    .format("json") \
    .save(f"s3://{bucket}/output/")


# Reading from Kafka (consumer)
df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", brokers) \
    .option("subscribe", topics) \
    .option("kafkaConsumer.pollTimeoutMs", 3000) \
    .option("includeHeaders", True) \
    .option("failOnDataLoss", "false") \
    .option("fetchOffset.numRetries", "5") \
    .option("fetchOffset.retryIntervalMs", "500") \
    .option("maxOffsetsPerTrigger", "2000") \
    .option("kafka.security.protocol", "SASL_SSL") \
    .option("kafka.sasl.mechanism", "AWS_MSK_IAM") \
    .option("kafka.sasl.jaas.config", "software.amazon.msk.auth.iam.IAMLoginModule required;") \
    .option("kafka.sasl.client.callback.handler.class", "software.amazon.msk.auth.iam.IAMClientCallbackHandler") \
    .load()


# Querying
query = df.writeStream \
    .queryName("EventStreaming") \
    .foreachBatch(process) \
    .trigger(processingTime="8 seconds") \
    .option("checkpointLocation",f"s3://{bucket}/checkpoints/{"_".join(topics)}") \
    .outputMode("append") \
    .start()

query.awaitTermination()

spark.close()