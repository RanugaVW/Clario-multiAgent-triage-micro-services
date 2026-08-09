FROM eclipse-temurin:21-jdk
VOLUME /tmp
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
COPY src src
RUN ./mvnw install -DskipTests
ENTRYPOINT ["java","-jar","target/ticket-core-service-0.0.1-SNAPSHOT.jar"]
