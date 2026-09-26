Testcontainers — Official Guides
================================

Source: https://testcontainers.com/guides/ (21 guides, listed 2026-09-26).
Read the guide that matches the user's stack, then translate it to current
library versions — most guides were written against testcontainers-java 1.x,
Node < 11 and Python < 4.15 (see *Version traps* in ``SKILL.md``).

The site's language filter lists Java, Go, .NET, Node.js, Python, Rust, Ruby,
PHP, Haskell, Clojure, Elixir, Scala and Native, but guides exist only for
the languages below. For the others, use the language docs in
``languages.rst``.

--------------

Start here
----------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Guide
     - Use when
   * - `What is Testcontainers, and why should you use it?
       <https://testcontainers.com/guides/introducing-testcontainers/>`_
     - Explaining the approach, or arguing against H2/mocks for a team.

Getting started, by language
----------------------------

Each builds a small PostgreSQL-backed repository test.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Language
     - Guide
   * - Java
     - https://testcontainers.com/guides/getting-started-with-testcontainers-for-java/
   * - Go
     - https://testcontainers.com/guides/getting-started-with-testcontainers-for-go/
   * - .NET
     - https://testcontainers.com/guides/getting-started-with-testcontainers-for-dotnet/
   * - Node.js
     - https://testcontainers.com/guides/getting-started-with-testcontainers-for-nodejs/
   * - Python
     - https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/

Java — Spring Boot
------------------

.. list-table::
   :header-rows: 1
   :widths: 45 25 30

   * - Guide
     - Tech
     - Use when
   * - `Getting started with Testcontainers in a Java Spring Boot Project
       <https://testcontainers.com/guides/testing-spring-boot-rest-api-using-testcontainers/>`_
     - PostgreSQL, REST Assured
     - Testing a REST API end to end against a real DB.
   * - `The simplest way to replace H2 with a real database for testing
       <https://testcontainers.com/guides/replace-h2-with-real-database-for-testing/>`_
     - PostgreSQL, H2
     - Migrating an H2-based suite (JDBC URL / ``@DataJpaTest``).
   * - `Testcontainers container lifecycle management using JUnit 5
       <https://testcontainers.com/guides/testcontainers-container-lifecycle/>`_
     - JUnit 5, PostgreSQL
     - Choosing per-method, per-class or singleton containers.
   * - `Testing Spring Boot Kafka Listener using Testcontainers
       <https://testcontainers.com/guides/testing-spring-boot-kafka-listener-using-testcontainers/>`_
     - Kafka, MySQL
     - Asserting async consumers (Awaitility).
   * - `Testing REST API integrations using WireMock
       <https://testcontainers.com/guides/testing-rest-api-integrations-using-wiremock/>`_
     - WireMock
     - Stubbing a third-party HTTP API.
   * - `Testing REST API integrations using MockServer
       <https://testcontainers.com/guides/testing-rest-api-integrations-using-mockserver/>`_
     - MockServer
     - Same, with MockServer expectations/verification.
   * - `Testing AWS service integrations using LocalStack
       <https://testcontainers.com/guides/testing-aws-service-integrations-using-localstack/>`_
     - LocalStack, S3, SQS
     - AWS SDK code (mind LocalStack auth-token requirements).
   * - `Working with jOOQ and Flyway using Testcontainers
       <https://testcontainers.com/guides/working-with-jooq-flyway-using-testcontainers/>`_
     - jOOQ, Flyway, PostgreSQL
     - Generating jOOQ code from a migrated schema at build time.
   * - `Securing Spring Boot Microservice using Keycloak and Testcontainers
       <https://testcontainers.com/guides/securing-spring-boot-microservice-using-keycloak-and-testcontainers/>`_
     - Keycloak, OAuth2
     - Testing resource-server security with real tokens.
   * - `Simple local development with Testcontainers Desktop
       <https://testcontainers.com/guides/simple-local-development-with-testcontainers-desktop/>`_
     - PostgreSQL, Testcontainers Desktop
     - Running the app locally against containers (``TestApplication`` main).

Java — other frameworks and topics
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 45 25 30

   * - Guide
     - Tech
     - Use when
   * - `Development and Testing of Quarkus applications using Testcontainers
       <https://testcontainers.com/guides/development-and-testing-quarkus-application-using-testcontainers/>`_
     - Quarkus, PostgreSQL, REST Assured
     - Quarkus Dev Services vs explicit containers.
   * - `Testing Micronaut Kafka Listener using Testcontainers
       <https://testcontainers.com/guides/testing-micronaut-kafka-listener-using-testcontainers/>`_
     - Micronaut, Kafka, MySQL
     - Micronaut Test Resources / Kafka consumers.
   * - `Testing REST API integrations in Micronaut applications using WireMock
       <https://testcontainers.com/guides/testing-rest-api-integrations-in-micronaut-apps-using-wiremock/>`_
     - Micronaut, WireMock
     - Stubbing HTTP clients in Micronaut.
   * - `Configuration of services running in a container
       <https://testcontainers.com/guides/configuration-of-services-running-in-container/>`_
     - PostgreSQL, LocalStack
     - Init scripts, copying files in, or running commands before tests.

.NET
----

.. list-table::
   :header-rows: 1
   :widths: 45 25 30

   * - Guide
     - Tech
     - Use when
   * - `Testing an ASP.NET Core web app
       <https://testcontainers.com/guides/testing-an-aspnet-core-web-app/>`_
     - ASP.NET Core, SQL Server, EF Core
     - ``WebApplicationFactory`` tests against a real SQL Server.
