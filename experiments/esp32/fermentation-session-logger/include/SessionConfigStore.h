#pragma once

#include <Arduino.h>
#include <FS.h>

class SessionConfigStore {
 public:
  bool begin(fs::FS& filesystem);
  bool ready() const { return ready_; }

  String floursJson() const;
  String presetsJson() const;
  String draftJson() const;
  String backupJson() const;

  String saveFlours(const String& body);
  String savePresets(const String& body);
  String saveDraft(const String& body);
  String importBackup(const String& body);

  bool draftValid(String* reason = nullptr) const;
  String draftName() const;
  String draftFlourSummary() const;
  float draftHydrationPercent() const;
  bool writeRecipeSnapshot(Print& output) const;

 private:
  bool ensureFile(const char* path, const char* defaultJson);
  bool recoverAtomicFile(const char* path);
  bool writeAtomic(const char* path, const String& content);
  bool fileExistsQuiet(const String& path) const;
  String readFile(const char* path, size_t maximumBytes) const;
  bool validateFlours(const String& content, String& error) const;
  bool validatePresets(const String& content, String& error,
                       const String* catalogOverride = nullptr) const;
  bool validateDraft(const String& content, String& error,
                     const String* catalogOverride = nullptr) const;
  bool validateDraftPresetReference(const String& draftContent,
                                    const String& presetsContent,
                                    String& error) const;
  String resultJson(bool ok, const String& message) const;

  fs::FS* filesystem_ = nullptr;
  bool ready_ = false;
};
