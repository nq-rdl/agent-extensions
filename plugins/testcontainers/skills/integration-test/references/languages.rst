Testcontainers — Supported Languages
====================================

Source: https://testcontainers.com/ (language list) and each project's
GitHub releases. Release versions were checked on 2026-09-26 — re-check the
linked docs before pinning, and prefer the project's current lockfile
version when one exists.

--------------

Language matrix
---------------

.. list-table::
   :header-rows: 1
   :widths: 12 38 22 28

   * - Language
     - Docs
     - Latest release
     - Install
   * - Java
     - https://java.testcontainers.org/
     - 2.0.5
     - ``org.testcontainers:testcontainers-<module>`` (Maven/Gradle, test scope)
   * - Go
     - https://golang.testcontainers.org/
     - v0.44.0
     - ``go get github.com/testcontainers/testcontainers-go/modules/<module>``
   * - .NET
     - https://dotnet.testcontainers.org/
     - 4.15.0
     - ``dotnet add package Testcontainers.<Module>``
   * - Node.js
     - https://node.testcontainers.org/
     - v12.1.0
     - ``npm i -D testcontainers @testcontainers/<module>``
   * - Python
     - https://testcontainers-python.readthedocs.io/en/latest/
     - 4.15.0
     - ``pip install "testcontainers[<module>]"``
   * - Rust
     - https://rust.testcontainers.org/
     - 0.28.0 (modules 0.15.0)
     - ``cargo add --dev testcontainers-modules --features <module>``
   * - Ruby
     - https://github.com/testcontainers/testcontainers-ruby
     - v0.2.0 (tag)
     - ``gem "testcontainers-core"`` + ``testcontainers-<module>``
   * - PHP
     - https://php.testcontainers.org
     - 1.1.0
     - ``composer require --dev testcontainers/testcontainers``
   * - Haskell
     - https://github.com/testcontainers/testcontainers-hs
     - 0.5.2.0
     - ``testcontainers`` (Hackage)
   * - Clojure
     - https://cljdoc.org/d/clj-test-containers/clj-test-containers/
     - see cljdoc
     - ``clj-test-containers/clj-test-containers`` (wraps Java)
   * - Elixir
     - https://github.com/testcontainers/testcontainers-elixir
     - v2.4.0
     - ``{:testcontainers, "~> 2.0", only: [:test]}``
   * - Scala
     - https://github.com/testcontainers/testcontainers-scala/
     - v0.44.1
     - ``com.dimafeng::testcontainers-scala-<module>`` (wraps Java)
   * - Native (C/C++ and FFI)
     - https://github.com/testcontainers/testcontainers-native
     - v0.1.0 (experimental)
     - Shared library built on testcontainers-go

Clojure and Scala wrap testcontainers-java, so Java runtime configuration
(``~/.testcontainers.properties``, Docker Engine 29 fix) applies to them.
Ruby, Haskell, Elixir, PHP and Native have smaller module sets — check the
repo before assuming a module exists; fall back to a generic container.

--------------

Java (2.x)
----------

JUnit 5 lifecycle: ``static`` field → one container per class; instance
field → one per test method (usually too slow).

.. code-block:: java

   import org.junit.jupiter.api.Test;
   import org.testcontainers.junit.jupiter.Container;
   import org.testcontainers.junit.jupiter.Testcontainers;
   import org.testcontainers.postgresql.PostgreSQLContainer;

   @Testcontainers
   class RepoTest {
       @Container
       static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:16-alpine");

       @Test
       void works() {
           String url = postgres.getJdbcUrl();
       }
   }

- Spring Boot 3.1+: annotate the container field with ``@ServiceConnection``
  (``spring-boot-testcontainers``) instead of ``@DynamicPropertySource``
  for supported services; use ``@DynamicPropertySource`` for the rest.
- Suite-wide singleton: start in a ``static {}`` block of an abstract base
  class and omit ``@Container``; Ryuk cleans up at JVM exit.
- JDBC URL shortcut (``jdbc:tc:postgresql:16:///db``) needs the module on
  the classpath; it creates a container per URL, per connection pool.

Go
--

.. code-block:: go

   import (
       "testing"

       "github.com/testcontainers/testcontainers-go"
       "github.com/testcontainers/testcontainers-go/modules/postgres"
   )

   func TestRepo(t *testing.T) {
       ctx := t.Context()
       pg, err := postgres.Run(ctx, "postgres:16-alpine",
           postgres.WithDatabase("app"),
           postgres.BasicWaitStrategies(),
       )
       testcontainers.CleanupContainer(t, pg) // nil-safe; call before the error check
       if err != nil {
           t.Fatal(err)
       }
       dsn := pg.MustConnectionString(ctx, "sslmode=disable")
       _ = dsn
   }

- ``testcontainers.Run(ctx, image, opts...)`` is the generic entry point;
  ``GenericContainer(ctx, GenericContainerRequest{...})`` is the older form.
- Package-wide container: start in ``TestMain`` and terminate after
  ``m.Run()``.
- Module ``Run`` functions differ in whether they wait by default — read
  the module's options for a wait helper.

.NET
----

xUnit: implement ``IAsyncLifetime`` on the test class (per class) or on a
fixture shared via ``IClassFixture<T>`` / ``ICollectionFixture<T>``.

.. code-block:: csharp

   using Testcontainers.PostgreSql;

   public sealed class RepoTests : IAsyncLifetime
   {
       private readonly PostgreSqlContainer _postgres =
           new PostgreSqlBuilder("postgres:16-alpine").Build();

       public Task InitializeAsync() => _postgres.StartAsync();
       public Task DisposeAsync() => _postgres.DisposeAsync().AsTask();

       [Fact]
       public void Works() => Assert.NotEmpty(_postgres.GetConnectionString());
   }

- ``Testcontainers.Xunit`` offers ``ContainerFixture``/``ContainerTest``
  base classes (also requires an explicit image since 4.10).
- ASP.NET Core: override the connection string in
  ``WebApplicationFactory<TProgram>.ConfigureWebHost``.

Node.js
-------

.. code-block:: typescript

   import { PostgreSqlContainer, StartedPostgreSqlContainer } from "@testcontainers/postgresql";

   let pg: StartedPostgreSqlContainer;

   beforeAll(async () => {
     pg = await new PostgreSqlContainer("postgres:16-alpine").start();
   }, 60_000);

   afterAll(async () => {
     await pg?.stop();
   });

   test("works", () => {
     expect(pg.getConnectionUri()).toContain("postgres");
   });

- Raise the hook timeout (Jest default 5 s, Vitest 10 s) — image pulls take
  longer.
- Jest/Vitest global setup can start shared containers once and pass
  connection details via environment variables.
- Supports ``await using`` (explicit resource management) on started
  containers.

Python
------

pytest: a ``scope="module"`` or ``scope="session"`` fixture that yields from
the context manager.

.. code-block:: python

   import pytest
   from testcontainers.community.postgres import PostgresContainer  # 4.15+

   @pytest.fixture(scope="module")
   def postgres():
       with PostgresContainer("postgres:16-alpine") as pg:
           yield pg

   def test_works(postgres):
       assert postgres.get_connection_url().startswith("postgresql")

- Before 4.15 the import is ``from testcontainers.postgres import
  PostgresContainer`` (still works on 4.15 with a ``DeprecationWarning``).
- Module extras install the driver: ``testcontainers[postgres]``.
- ``get_connection_url()`` returns a SQLAlchemy URL including the driver
  (``postgresql+psycopg2://``); pass ``driver=None`` for a plain URL.

Rust
----

.. code-block:: rust

   use testcontainers_modules::{postgres::Postgres, testcontainers::{runners::AsyncRunner, ImageExt}};

   #[tokio::test]
   async fn works() -> Result<(), Box<dyn std::error::Error>> {
       let node = Postgres::default().with_tag("16-alpine").start().await?;
       let port = node.get_host_port_ipv4(5432).await?;
       let host = node.get_host().await?;
       // Module defaults: user, password and database are all "postgres".
       let _conn = format!("host={host} port={port} user=postgres password=postgres");
       Ok(())
   }

- ``SyncRunner`` needs the ``blocking`` feature; ``AsyncRunner`` needs a
  Tokio runtime.
- The container is removed when the ``ContainerAsync``/``Container`` value
  is dropped — keep it alive for the whole test.
