#pragma once

#include <Arduino.h>
#include <WebServer.h>

#include <functional>

class WebInterface {
 public:
  using JsonHandler = std::function<String()>;

  WebInterface();
  void configure(JsonHandler statusHandler, JsonHandler testHandler,
                 JsonHandler toggleHandler);
  bool begin();
  void stop();
  void tick();
  bool running() const { return running_; }

 private:
  void configureRoutes();
  void sendJson(const JsonHandler& handler);

  WebServer server_;
  JsonHandler statusHandler_;
  JsonHandler testHandler_;
  JsonHandler toggleHandler_;
  bool routesConfigured_ = false;
  bool running_ = false;
};
