# Project SAM Portfolio Backend

Serverless backend for the portfolio site. It provides HTTP API endpoints for
blogs and projects using AWS Lambda, DynamoDB, API Gateway HTTP API, and
GitHub Actions deployment.

## Structure

```text
project-sam/
├── .github/workflows/deploy.yml
├── apigateway/portfolio/template.yaml
├── dynamodb/
│   ├── blogs/template.yaml
│   └── projects/template.yaml
├── lambda/
│   ├── blogs/
│   │   ├── app.py
│   │   ├── shared_utils.py
│   │   ├── requirements.txt
│   │   └── template.yaml
│   └── projects/
│       ├── app.py
│       ├── shared_utils.py
│       ├── requirements.txt
│       └── template.yaml
├── template.yaml
└── samconfig.toml
```

## API

Blogs:

```text
GET    /blogs
GET    /blogs/{id}
POST   /blogs
PUT    /blogs/{id}
DELETE /blogs/{id}
```

Projects:

```text
GET    /projects
GET    /projects/{id}
POST   /projects
PUT    /projects/{id}
DELETE /projects/{id}
```

## Deploy

```bash
sam build
sam deploy
```

GitHub Actions deploys the stack on pushes to `main`.

## CloudFormation Outputs

After deployment, use these outputs:

```text
PortfolioApi
BlogsApi
ProjectsApi
BlogsDynamoDBTableName
ProjectsDynamoDBTableName
```

Set the frontend `portfolio/config.js` value to `PortfolioApi`:

```js
window.PORTFOLIO_API_BASE_URL = "https://xxxxx.execute-api.ap-southeast-1.amazonaws.com";
```

## Test

Create a blog:

```bash
curl -i -X POST "$BLOGS_API" \
  -H "Content-Type: application/json" \
  -d '{"id":"blog-001","title":"First Blog","slug":"first-blog","summary":"Short summary","content":"Markdown content","tags":["aws","serverless"],"status":"published"}'
```

Create a project:

```bash
curl -i -X POST "$PROJECTS_API" \
  -H "Content-Type: application/json" \
  -d '{"id":"project-001","name":"Portfolio Backend","slug":"portfolio-backend","summary":"Serverless backend","description":"Blogs and projects API","techStack":["AWS SAM","Lambda","DynamoDB"],"status":"published"}'
```
