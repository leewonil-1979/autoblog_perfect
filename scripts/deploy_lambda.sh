#!/bin/bash
# Lambda 배포 스크립트 (Linux/Mac)
set -e

FUNCTION_NAME="${1:-blog-automation}"
REGION="${2:-ap-northeast-2}"

echo "🚀 Lambda 배포 시작..."

# 1. 디렉토리 설정
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAMBDA_DIR="$PROJECT_ROOT/lambda"
PACKAGE_DIR="$LAMBDA_DIR/package"
ZIP_FILE="$LAMBDA_DIR/lambda.zip"

cd "$LAMBDA_DIR"

# 2. 이전 빌드 정리
echo -e "\n[1/5] 이전 빌드 정리..."
rm -rf "$PACKAGE_DIR" "$ZIP_FILE"
echo "  ✅ 정리 완료"

# 3. 의존성 설치
echo -e "\n[2/5] 의존성 설치..."
mkdir -p "$PACKAGE_DIR"
pip install -r requirements.txt -t "$PACKAGE_DIR" --no-cache-dir
echo "  ✅ 패키지 설치 완료"

# 4. 코드 복사
echo -e "\n[3/5] 코드 복사..."
cp handler.py render.py "$PACKAGE_DIR/"
echo "  ✅ handler.py, render.py 복사됨"

# 5. ZIP 생성
echo -e "\n[4/5] ZIP 패키지 생성..."
cd "$PACKAGE_DIR"
zip -r "$ZIP_FILE" . > /dev/null
cd "$LAMBDA_DIR"
ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "  ✅ lambda.zip 생성 ($ZIP_SIZE)"

# 6. AWS 배포
echo -e "\n[5/5] AWS Lambda 업데이트..."
if aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://lambda.zip" \
    --region "$REGION" > /dev/null 2>&1; then
    echo "  ✅ 배포 완료: $FUNCTION_NAME ($REGION)"
else
    echo "  ⚠️  update-function-code 실패. 함수가 없으면 create-function을 실행하세요."
fi

echo -e "\n✅ 배포 프로세스 완료!"
echo -e "\n다음 단계:"
echo "  1. Lambda 콘솔에서 환경 변수 설정"
echo "  2. EventBridge 스케줄 생성"
echo "  3. CloudWatch Logs 확인"
