FROM jenkins/jenkins:lts-jdk17

USER root

# Install OpenJDK 25, Maven, and Git for compiling and deploying modern Spring Boot apps
RUN apt-get update && \
    apt-get install -y --no-install-recommends git maven openjdk-25-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER jenkins
