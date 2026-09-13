FROM eclipse-temurin:21-jdk AS build
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
COPY src src
# mvnw is checked out with CRLF on Windows; strip CR so the shebang resolves.
RUN sed -i 's/\r$//' mvnw && chmod +x mvnw && ./mvnw install -DskipTests

FROM eclipse-temurin:21-jre
VOLUME /tmp
COPY --from=build /target/api-gateway-0.0.1-SNAPSHOT.jar app.jar
ENTRYPOINT ["java","-jar","app.jar"]
