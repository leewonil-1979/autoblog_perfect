# tools/s3_publish.py
# 목적: 단일 파일을 S3에 업로드하고, 지정 만료시간의 프리사인 URL을 생성해 출력
# 가정: 버킷은 ACL 비활성(권장). presign 용으로 s3:GetObject 권한 부여됨.
# 사용:
#   python tools/s3_publish.py --file dist/post.html --key posts/2025-10-13-post.html --expires 900
# 출력: 프리사인 URL 1줄

from __future__ import annotations

import argparse
import logging
import mimetypes
import os
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def get_s3_client(profile: Optional[str] = None):
    """
    boto3 세션/클라이언트 생성.
    - 환경변수(.env) 또는 --profile 사용
    """
    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    try:
        session = boto3.Session(**session_kwargs)
        region = os.getenv("AWS_REGION", "ap-northeast-2")
        # 시계 편차에 민감한 서명 오류 방지: 적절한 리트라이/서명 설정
        return session.client("s3", region_name=region, config=Config(signature_version="s3v4"))
    except Exception:
        logging.exception("S3 클라이언트 생성 실패")
        raise

def guess_content_type(path: str) -> str:
    """파일 확장자 기반 Content-Type 추정. 기본값 text/plain."""
    ctype, _ = mimetypes.guess_type(path)
    return ctype or "text/plain"

def upload_file(
    s3,
    bucket: str,
    src_path: str,
    key: str,
    cache_control: Optional[str] = None,
) -> None:
    """
    파일 업로드. ACL 비활성 버킷 가정: ExtraArgs에 ACL 미지정.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"소스 파일이 존재하지 않습니다: {src_path}")
    extra_args = {"ContentType": guess_content_type(src_path)}
    if cache_control:
        extra_args["CacheControl"] = cache_control
    try:
        s3.upload_file(src_path, bucket, key, ExtraArgs=extra_args)
        logging.info("업로드 성공: s3://%s/%s (%s)", bucket, key, extra_args["ContentType"])
    except ClientError:
        logging.exception("S3 업로드 실패(ClientError)")
        raise
    except BotoCoreError:
        logging.exception("S3 업로드 실패(BotoCoreError)")
        raise

def presign_url(s3, bucket: str, key: str, expires: int) -> str:
    """
    객체에 대한 프리사인 GET URL 생성.
    - 정책에 s3:GetObject 허용 필요
    """
    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
        logging.info("프리사인 URL 생성 완료(만료 %s초)", expires)
        return url
    except ClientError:
        logging.exception("프리사인 URL 생성 실패(ClientError)")
        raise
    except BotoCoreError:
        logging.exception("프리사인 URL 생성 실패(BotoCoreError)")
        raise

def main():
    load_dotenv()  # .env 로드
    parser = argparse.ArgumentParser(description="S3 업로드 + 프리사인 URL 생성")
    parser.add_argument("--file", required=True, help="업로드할 로컬 파일 경로")
    parser.add_argument("--key", required=True, help="S3 객체 키(ex. posts/2025-10-13-slug.html)")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_TISTORY", "blog-auto-mvp"))
    parser.add_argument("--expires", type=int, default=900, help="프리사인 URL 만료(초), 기본 900")
    parser.add_argument("--cache", default=None, help="Cache-Control 헤더 값(옵션)")
    parser.add_argument("--profile", default=None, help="AWS CLI 프로파일명(옵션)")
    args = parser.parse_args()

    s3 = get_s3_client(profile=args.profile)
    upload_file(s3, args.bucket, args.file, args.key, cache_control=args.cache)
    url = presign_url(s3, args.bucket, args.key, expires=args.expires)

    # 파이프라인에서 쉽게 사용할 수 있게 표준출력에 URL만 출력
    print(url)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("실패: %s", e)
        raise
