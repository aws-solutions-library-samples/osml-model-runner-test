def split_s3_path(s3_path: str) -> tuple[str, str]:
    """
    Split an S3 path into bucket and key components.

    :param s3_path: Full S3 path in the format 's3://bucket/path/to/object'
                   (supports s3://, https://, or path-style formats)
    :return: Tuple of (bucket_name, object_key)

    Examples:
        >>> split_s3_path("s3://my-bucket/path/to/file.txt")
        ('my-bucket', 'path/to/file.txt')
        >>> split_s3_path("https://XXXXXXXXXXXXXXXXXXXXXXXXXX/path/to/file.txt")
        ('my-bucket', 'path/to/file.txt')
        >>> split_s3_path("https://s3.amazonaws.com/my-bucket/path/to/file.txt")
        ('my-bucket', 'path/to/file.txt')
    """
    # Remove any protocol prefix (s3:// or https://)
    if s3_path.startswith("s3://"):
        path = s3_path[5:]
    elif s3_path.startswith("https://"):
        path = s3_path[8:]
    else:
        path = s3_path

    # Handle virtual hosted-style URLs (XXXXXXXXXXXXXXXXXXXXXXX)
    if ".s3." in path:
        parts = path.split("/", 1)
        bucket = parts[0].split(".s3.")[0]
        prefix = parts[1] if len(parts) > 1 else ""
        return bucket, prefix

    # Handle path-style URLs (s3.amazonaws.com/bucket) and s3:// paths
    parts = path.split("/", 1)
    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[1]
