FROM eclipse-temurin:21-jdk
VOLUME /tmp
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
COPY src src
# mvnw is checked out with CRLF on Windows; strip CR so the shebang resolves.
RUN sed -i 's/\r$//' mvnw && chmod +x mvnw && ./mvnw install -DskipTests
ENTRYPOINT ["java","-jar","target/ticket-core-service-0.0.1-SNAPSHOT.jar"]
