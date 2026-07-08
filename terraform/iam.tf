data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_app_role" {
  name               = "${var.project_name}-${var.environment}-ec2-app-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_instance_profile" "ec2_app_profile" {
  name = "${var.project_name}-${var.environment}-ec2-app-profile"
  role = aws_iam_role.ec2_app_role.name
}

data "aws_iam_policy_document" "ec2_s3_policy" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.backend_media.arn,
      "${aws_s3_bucket.backend_media.arn}/*"
    ]
  }
}

resource "aws_iam_role_policy" "ec2_s3_access" {
  name   = "${var.project_name}-${var.environment}-ec2-s3-access"
  role   = aws_iam_role.ec2_app_role.id
  policy = data.aws_iam_policy_document.ec2_s3_policy.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_app_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
