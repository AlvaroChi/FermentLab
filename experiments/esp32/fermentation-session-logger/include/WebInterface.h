#pragma once

#include <Arduino.h>
#include <WebServer.h>

#include <functional>

class ObservableWebServer : public WebServer {
 public:
  explicit ObservableWebServer(uint16_t port) : WebServer(port) {}

  bool listening() { return static_cast<bool>(_server); }
};

class WebInterface {
 public:
  using JsonHandler = std::function<String()>;
  using JsonBodyHandler = std::function<String(const String&)>;

  WebInterface();
  void configure(JsonHandler statusHandler, JsonHandler testHandler,
                 JsonHandler toggleHandler);
  void configureRecipes(JsonHandler floursHandler,
                        JsonBodyHandler saveFloursHandler,
                        JsonHandler presetsHandler,
                        JsonBodyHandler savePresetsHandler,
                        JsonHandler draftHandler,
                        JsonBodyHandler saveDraftHandler,
                        JsonHandler backupHandler,
                        JsonBodyHandler importHandler);
  bool begin();
  void stop();
  void tick();
  bool running();
  bool mdnsReady() const { return mdnsReady_; }

 private:
  void configureRoutes();
  void sendJson(const JsonHandler& handler);
  void sendJsonBody(const JsonBodyHandler& handler);

  ObservableWebServer server_;
  JsonHandler statusHandler_;
  JsonHandler testHandler_;
  JsonHandler toggleHandler_;
  JsonHandler floursHandler_;
  JsonBodyHandler saveFloursHandler_;
  JsonHandler presetsHandler_;
  JsonBodyHandler savePresetsHandler_;
  JsonHandler draftHandler_;
  JsonBodyHandler saveDraftHandler_;
  JsonHandler backupHandler_;
  JsonBodyHandler importHandler_;
  bool routesConfigured_ = false;
  bool running_ = false;
  bool mdnsReady_ = false;
  uint32_t nextStartAttemptMs_ = 0;
};
