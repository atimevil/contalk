# ============================================================
# 계약똑똑 AWS 인프라 — Phase 1 개발 환경
# Terraform >= 1.6 / AWS Provider ~> 5.0
#
# 포함 리소스:
#   - VPC + 퍼블릭 서브넷 2개 (AZ: a, c)
#   - EC2 t3.small 1대 (백엔드 + Docker)
#   - RDS PostgreSQL t3.micro
#   - S3 버킷 2개 (계약서 파일, 프론트엔드)
#   - Security Groups
#   - CloudFront Distribution (프론트엔드)
# ============================================================

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 팀 협업 시 S3 백엔드로 전환 권장
  # backend "s3" {
  #   bucket = "contalktok-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "ap-northeast-2"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = var.common_tags
  }
}

# ─────────────────────────────────────────
# 데이터 소스
# ─────────────────────────────────────────
data "aws_caller_identity" "current" {}

# ─────────────────────────────────────────
# VPC
# ─────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc"
  }
}

# 인터넷 게이트웨이
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment}-igw"
  }
}

# ─────────────────────────────────────────
# 퍼블릭 서브넷 (2개)
# ─────────────────────────────────────────
resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-${var.environment}-public-subnet-${count.index + 1}"
    Tier = "public"
  }
}

# 라우팅 테이블 (퍼블릭)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ─────────────────────────────────────────
# Security Groups
# ─────────────────────────────────────────

# EC2 Security Group
resource "aws_security_group" "backend" {
  name        = "${var.project_name}-${var.environment}-backend-sg"
  description = "Backend EC2 Security Group"
  vpc_id      = aws_vpc.main.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # 프로덕션에서는 특정 IP로 제한할 것
  }

  # HTTP
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI (개발 단계 — 직접 접근 허용)
  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # 모든 아웃바운드 허용
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-sg"
  }
}

# RDS Security Group (EC2에서만 접근)
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "RDS PostgreSQL Security Group"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }
}

# ─────────────────────────────────────────
# EC2 — 백엔드 서버 (t3.small)
# ─────────────────────────────────────────
resource "aws_instance" "backend" {
  ami                    = var.ec2_ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.backend.id]
  key_name               = var.key_pair_name

  # 루트 볼륨 30GiB (Docker 이미지 공간 확보)
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  # EC2 시작 시 Docker + Docker Compose 자동 설치
  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -e
    yum update -y

    # Docker 설치 (Amazon Linux 2023)
    yum install -y docker git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user

    # Docker Compose v2 설치
    COMPOSE_VERSION="v2.24.5"
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL \
      "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    echo "EC2 bootstrap complete"
  EOT
  )

  tags = {
    Name = "${var.project_name}-${var.environment}-backend"
    Role = "backend"
  }
}

# Elastic IP (고정 IP)
resource "aws_eip" "backend" {
  instance = aws_instance.backend.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-eip"
  }
}

# ─────────────────────────────────────────
# RDS — PostgreSQL (db.t3.micro)
# ─────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name        = "${var.project_name}-${var.environment}-db-subnet-group"
  description = "DB subnet group for ${var.project_name}"
  subnet_ids  = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-${var.environment}-db-subnet-group"
  }
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 100 # Auto-scaling 상한 (GiB)
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Phase 1 개발 환경: Multi-AZ 비활성화 (비용 절감)
  multi_az = false

  # Phase 1 개발 환경: 퍼블릭 접근 비활성화
  publicly_accessible = false

  # 자동 백업 (7일 보존)
  backup_retention_period = 7
  backup_window           = "03:00-04:00" # UTC (KST 12:00-13:00)
  maintenance_window      = "sun:04:00-sun:05:00"

  # 삭제 보호 (프로덕션에서는 true로)
  deletion_protection = false

  # Terraform destroy 시 최종 스냅샷 생성
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-${var.environment}-final-snapshot"

  tags = {
    Name = "${var.project_name}-${var.environment}-postgres"
  }
}

# ─────────────────────────────────────────
# S3 — 계약서 파일 버킷
# ─────────────────────────────────────────
resource "aws_s3_bucket" "contracts" {
  bucket        = var.s3_contract_bucket_name
  force_destroy = false # 실수로 인한 삭제 방지

  tags = {
    Name    = var.s3_contract_bucket_name
    Purpose = "contract-storage"
  }
}

# 퍼블릭 접근 차단 (계약서는 Presigned URL로만 접근)
resource "aws_s3_bucket_public_access_block" "contracts" {
  bucket = aws_s3_bucket.contracts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 서버 측 암호화
resource "aws_s3_bucket_server_side_encryption_configuration" "contracts" {
  bucket = aws_s3_bucket.contracts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle 정책 (30일 후 Glacier Instant Retrieval로 전환)
resource "aws_s3_bucket_lifecycle_configuration" "contracts" {
  bucket = aws_s3_bucket.contracts.id

  rule {
    id     = "contract-lifecycle"
    status = "Enabled"

    filter {
      prefix = "contracts/"
    }

    # 30일 후 Glacier Instant Retrieval로 전환 (약 80% 비용 절감)
    transition {
      days          = var.contract_lifecycle_days
      storage_class = "GLACIER_IR"
    }

    # 365일 후 Deep Archive로 전환
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    # 3년 후 삭제 (법적 보존 기간 고려 — 필요 시 수정)
    expiration {
      days = 1095
    }
  }
}

# CORS 설정 (프론트엔드 → S3 직접 업로드 허용)
resource "aws_s3_bucket_cors_configuration" "contracts" {
  bucket = aws_s3_bucket.contracts.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["https://contalktok.kr", "http://localhost:3000"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# ─────────────────────────────────────────
# S3 — 프론트엔드 정적 파일 버킷
# ─────────────────────────────────────────
resource "aws_s3_bucket" "frontend" {
  bucket        = var.s3_frontend_bucket_name
  force_destroy = true # 정적 파일은 재빌드 가능

  tags = {
    Name    = var.s3_frontend_bucket_name
    Purpose = "frontend-hosting"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ─────────────────────────────────────────
# CloudFront — 프론트엔드 배포
# ─────────────────────────────────────────
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-${var.environment}-oac"
  description                       = "OAC for ${var.project_name} frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "${var.project_name} ${var.environment} frontend"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-${var.s3_frontend_bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${var.s3_frontend_bucket_name}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # React SPA — 404를 index.html로 리다이렉트
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  price_class = "PriceClass_200" # 아시아 태평양 + 미국/유럽

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    # 커스텀 도메인 연결 시:
    # acm_certificate_arn      = aws_acm_certificate.main.arn
    # ssl_support_method       = "sni-only"
    # minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-cf"
  }
}

# S3 버킷 정책 (CloudFront OAC 허용)
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}

# ─────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────
output "backend_public_ip" {
  description = "EC2 백엔드 서버 Elastic IP"
  value       = aws_eip.backend.public_ip
}

output "backend_public_dns" {
  description = "EC2 백엔드 서버 퍼블릭 DNS"
  value       = aws_instance.backend.public_dns
}

output "rds_endpoint" {
  description = "RDS PostgreSQL 엔드포인트"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS PostgreSQL 포트"
  value       = aws_db_instance.postgres.port
}

output "s3_contract_bucket" {
  description = "계약서 파일 S3 버킷 이름"
  value       = aws_s3_bucket.contracts.bucket
}

output "s3_frontend_bucket" {
  description = "프론트엔드 S3 버킷 이름"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_domain" {
  description = "CloudFront 배포 도메인"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront Distribution ID (GitHub Actions Secrets에 등록)"
  value       = aws_cloudfront_distribution.frontend.id
}
