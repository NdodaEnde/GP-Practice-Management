#!/bin/bash

# SurgiScan Document Processing Microservice Deployment Script
# This script helps deploy the microservice to various environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_status "Docker found: $(docker --version)"
}

# Check if Docker Compose is installed
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_status "Docker Compose found: $(docker-compose --version)"
}

# Validate environment file
check_env_file() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your configuration before proceeding."
        read -p "Press enter to continue after editing .env file..."
    else
        print_status ".env file found"
    fi
}

# Build Docker image
build_image() {
    print_status "Building Docker image..."
    docker build -t surgiscan-document-processor:latest .
    print_status "Docker image built successfully"
}

# Deploy to local development
deploy_local() {
    print_header "DEPLOYING TO LOCAL DEVELOPMENT"
    
    check_docker
    check_docker_compose
    check_env_file
    
    print_status "Starting services with Docker Compose..."
    docker-compose up -d
    
    print_status "Waiting for services to start..."
    sleep 10
    
    # Check health
    print_status "Checking service health..."
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_status "✅ Service is healthy and running!"
        echo ""
        echo "Service URLs:"
        echo "  - API: http://localhost:8000"
        echo "  - Health Check: http://localhost:8000/health"
        echo "  - API Docs: http://localhost:8000/docs"
        echo "  - MongoDB Express: http://localhost:8081 (admin/admin123)"
        echo ""
        echo "To view logs: docker-compose logs -f"
        echo "To stop: docker-compose down"
    else
        print_error "❌ Service health check failed"
        print_status "Showing logs..."
        docker-compose logs app
    fi
}

# Deploy to production (Render)
deploy_render() {
    print_header "DEPLOYING TO RENDER"
    
    # Check if git is configured
    if ! git status &> /dev/null; then
        print_error "Not in a git repository. Initialize git first:"
        echo "  git init"
        echo "  git add ."
        echo "  git commit -m 'Initial commit'"
        echo "  git remote add origin YOUR_REPO_URL"
        exit 1
    fi
    
    print_status "Checking git status..."
    if [ -n "$(git status --porcelain)" ]; then
        print_warning "You have uncommitted changes. Committing..."
        git add .
        git commit -m "Deploy to Render: $(date)"
    fi
    
    print_status "Pushing to git repository..."
    git push origin main
    
    echo ""
    print_status "Next steps for Render deployment:"
    echo "1. Go to https://render.com and sign in"
    echo "2. Click 'New +' -> 'Web Service'"
    echo "3. Connect your GitHub repository"
    echo "4. Use these settings:"
    echo "   - Build Command: (leave empty - using Dockerfile)"
    echo "   - Start Command: (leave empty - using Dockerfile)"
    echo "5. Set environment variables in Render dashboard"
    echo "6. Deploy!"
    echo ""
    print_warning "Don't forget to set up MongoDB database service in Render"
}

# Test the deployment
test_deployment() {
    local BASE_URL=${1:-http://localhost:8000}
    
    print_header "TESTING DEPLOYMENT"
    print_status "Testing deployment at: $BASE_URL"
    
    # Test health check
    print_status "Testing health check..."
    if curl -f "$BASE_URL/health" &> /dev/null; then
        print_status "✅ Health check passed"
    else
        print_error "❌ Health check failed"
        return 1
    fi
    
    # Test API endpoints (if API key is not required)
    print_status "Testing API endpoints..."
    
    # Test statistics endpoint
    if curl -f "$BASE_URL/api/v1/statistics" &> /dev/null; then
        print_status "✅ Statistics endpoint accessible"
    else
        print_warning "⚠️ Statistics endpoint requires authentication or is not available"
    fi
    
    print_status "✅ Basic tests passed"
}

# Clean up development environment
cleanup() {
    print_header "CLEANING UP"
    
    print_status "Stopping Docker Compose services..."
    docker-compose down
    
    print_status "Removing unused Docker images..."
    docker image prune -f
    
    print_status "✅ Cleanup complete"
}

# Show usage
show_usage() {
    echo "SurgiScan Document Processing Microservice Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  local      Deploy to local development environment"
    echo "  render     Prepare and guide Render deployment"
    echo "  test       Test the deployment"
    echo "  build      Build Docker image only"
    echo "  cleanup    Clean up development environment"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local                    # Deploy locally"
    echo "  $0 test                     # Test local deployment"
    echo "  $0 test https://your-app.onrender.com  # Test remote deployment"
    echo "  $0 render                   # Deploy to Render"
    echo "  $0 cleanup                  # Clean up"
}

# Main script logic
case "${1:-help}" in
    "local")
        deploy_local
        ;;
    "render")
        deploy_render
        ;;
    "test")
        test_deployment "$2"
        ;;
    "build")
        check_docker
        build_image
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|"--help"|"-h")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac