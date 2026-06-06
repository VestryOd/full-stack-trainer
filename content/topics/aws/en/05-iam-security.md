# IAM and Security

## What is IAM

IAM stands for:

```txt
Identity and Access Management
```

---

It is the system of:

```txt
Authentication
Authorization
```

in AWS.

---

# Very Important

Authentication:

```txt
Who are you?
```

---

Authorization:

```txt
What are you allowed to do?
```

---

IAM handles both.

---

# The Main Purpose of IAM

To determine:

```txt
Who

What

On what

Can do
```

---

# Core Entities

```txt
User

Group

Role

Policy
```

---

# User

A physical user.

---

For example:

```txt
Maxim
Alice
Admin
```

---

A user receives:

```txt
Login
Password
Access Keys
```

---

# Group

A group of users.

---

For example:

```txt
Developers

Admins

QA
```

---

Permissions are assigned to the group.

---

# Policy

The most important entity.

---

A Policy defines:

```txt
what is allowed
```

---

Example:

```json
{
 "Effect": "Allow",
 "Action": "s3:GetObject",
 "Resource": "*"
}
```

---

Which means:

```txt
can read S3 objects
```

---

# Action

Interviewers love asking this.

---

Examples:

```txt
s3:GetObject

s3:PutObject

lambda:InvokeFunction

dynamodb:GetItem
```

---

# Resource

What the permission applies to.

---

For example:

```txt
a specific bucket

a specific lambda
```

---

# Effect

```txt
Allow
```

or

```txt
Deny
```

---

# Principle of Least Privilege

The most popular question.

---

Principle:

```txt
minimum necessary permissions
```

---

Bad:

```txt
AdministratorAccess
```

---

For everyone.

---

Good:

```txt
only the required permissions
```

---

# Role

A very important topic.

---

A Role is a set of permissions
that a service can temporarily assume.

---

# Why Role is More Important Than User

Interviewers love asking this.

---

For example:

```txt
Lambda
```

is not a user.

---

But it needs access to:

```txt
S3
DynamoDB
SQS
```

---

We use:

```txt
IAM Role
```

---

# Lambda Role

Diagram:

```txt
Lambda
 ↓
Assume Role
 ↓
S3 Access
```

---

Without Access Keys.

---

# Why This Is More Secure

No need to store:

```txt
AWS_ACCESS_KEY

AWS_SECRET_KEY
```

---

In the code.

---

# Temporary Credentials

Very popular interview question.

---

When a service assumes a role.

---

AWS issues:

```txt
temporary credentials
```

---

For a limited time.

---

# Trust Policy

A very interesting topic.

---

Defines:

```txt
who can use the role
```

---

For example:

```txt
Lambda Service
```

---

Or:

```txt
EC2 Service
```

---

# Permission Policy

Defines:

```txt
what can be done
```

---

# Flow

```txt
Lambda
 ↓
Role
 ↓
Policy
 ↓
S3
```

---

# Secrets

Very popular interview question.

---

You cannot store:

```txt
passwords

tokens

api keys
```

---

In the code.

---

Use:

```txt
Secrets Manager

Parameter Store
```

---

# Common Question

How does Lambda get access to S3?

Answer:

Through an IAM Role assigned to the Lambda function. The role contains a Policy with permission to access the required Bucket.

---

# Common Question

What is an IAM Role?

Answer:

A set of permissions that an AWS service or user can temporarily assume.

---

# Common Question

Why is an IAM Role better than Access Keys?

Answer:

It doesn't require storing secrets and uses temporary credentials.

---

# Interview Answer

IAM manages access control in AWS. The core entities are Users, Roles, and Policies. In production systems, services typically use IAM Roles instead of Access Keys, which allows them to securely obtain temporary permissions to access AWS resources.
