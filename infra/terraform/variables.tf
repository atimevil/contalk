# ============================================================
# 계약똑똑 Terraform 변수 정의
# 실제 값은 terraform.tfvars 파일에 작성하거나
# 실행 시 -var 옵션으로 전달하세요.
# ============================================================

# ─────────────────────────────────────────
# AWS 기본 설정
# ─────────────────────────────────────────
variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "aws_profile" {
  description = "AWS CLI 프로파일 이름 (로컬 개발용)"
  type        = string
  default     = "default"
}

# ─────────────────────────────────────────
# 프로젝트 식별
# ─────────────────────────────────────────
variable "project_name" {
  description = "프로젝트 이름 (리소스 태그 및 이름 prefix에 사용)"
  type        = string
  default     = "contalktok"
}

variable "environment" {
  description = "배포 환경 (dev / staging / prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment는 dev, staging, prod 중 하나여야 합니다."
  }
}

# ─────────────────────────────────────────
# 네트워크
# ─────────────────────────────────────────
variable "vpc_cidr" {
  description = "VPC CIDR 블록"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "퍼블릭 서브넷 CIDR 목록 (가용 영역별)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "availability_zones" {
  description = "사용할 가용 영역 목록"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

# ─────────────────────────────────────────
# EC2 백엔드 서버
# ─────────────────────────────────────────
variable "instance_type" {
  description = "EC2 인스턴스 타입"
  type        = string
  default     = "t3.small"
}

variable "key_pair_name" {
  description = "EC2 SSH 키 페어 이름 (AWS에 미리 등록 필요)"
  type        = string
  default     = "contalktok-key"
}

variable "ec2_ami_id" {
  description = "EC2 AMI ID (Amazon Linux 2023, ap-northeast-2)"
  type        = string
  # Amazon Linux 2023 (ap-northeast-2) — 주기적으로 최신 버전 확인 필요
  default = "ami-0f1e61a80c7ab943e"
}

# ─────────────────────────────────────────
# RDS PostgreSQL
# ─────────────────────────────────────────
variable "db_instance_class" {
  description = "RDS 인스턴스 클래스"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "RDS 데이터베이스 이름"
  type        = string
  default     = "contalktok"
}

variable "db_username" {
  description = "RDS 마스터 사용자 이름"
  type        = string
  default     = "contalktok_admin"
  sensitive   = true
}

variable "db_password" {
  description = "RDS 마스터 비밀번호 (16자 이상 권장)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 16
    error_message = "db_password는 최소 16자 이상이어야 합니다."
  }
}

variable "db_allocated_storage" {
  description = "RDS 스토리지 크기 (GiB)"
  type        = number
  default     = 20
}

# ─────────────────────────────────────────
# S3 버킷
# ─────────────────────────────────────────
variable "s3_contract_bucket_name" {
  description = "계약서 파일 저장 S3 버킷 이름 (전역 유일해야 함)"
  type        = string
  default     = "contalktok-contracts"
}

variable "s3_frontend_bucket_name" {
  description = "프론트엔드 정적 파일 S3 버킷 이름"
  type        = string
  default     = "contalktok-frontend"
}

variable "contract_lifecycle_days" {
  description = "계약서 파일 S3 Lifecycle 전환 일수 (Glacier IA)"
  type        = number
  default     = 30
}

# ─────────────────────────────────────────
# 태그
# ─────────────────────────────────────────
variable "common_tags" {
  description = "모든 AWS 리소스에 공통으로 붙는 태그"
  type        = map(string)
  default = {
    Project     = "contalktok"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}
