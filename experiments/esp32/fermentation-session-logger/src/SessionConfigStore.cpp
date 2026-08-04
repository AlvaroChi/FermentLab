#include "SessionConfigStore.h"

#include <ArduinoJson.h>

#include <cmath>

#include "Config.h"

namespace {

const char DEFAULT_FLOURS[] PROGMEM = R"JSON({
  "schema":"fermentlab.flours.v1",
  "revision":1,
  "items":[
    {
      "id":"caputo-pizzeria",
      "brand":"Mulino Caputo",
      "name":"Pizzeria",
      "type":"00",
      "protein_pct":12.5,
      "w_min":260,
      "w_max":280,
      "pl_min":0.5,
      "pl_max":0.6,
      "notes":"Per impasti tradizionali e pizza napoletana.",
      "source_url":"https://www.mulinocaputo.it/prodotti/pizzeria/",
      "verified":true
    },
    {
      "id":"caputo-nuvola",
      "brand":"Mulino Caputo",
      "name":"Nuvola",
      "type":"0",
      "protein_pct":12.5,
      "w_min":270,
      "w_max":290,
      "pl_min":0.5,
      "pl_max":0.6,
      "notes":"Per focaccia, pizza in teglia e pizza contemporanea.",
      "source_url":"https://www.mulinocaputo.it/prodotti/nuvola/",
      "verified":true
    },
    {
      "id":"italiamo-nuvola",
      "brand":"Italiamo (Lidl)",
      "name":"Nuvola",
      "type":null,
      "protein_pct":null,
      "w_min":null,
      "w_max":null,
      "pl_min":null,
      "pl_max":null,
      "notes":"Prodotto precaricato. Completare i dati tecnici leggendo l'etichetta della propria confezione.",
      "source_url":"",
      "verified":false
    }
  ]
})JSON";

const char DEFAULT_PRESETS[] PROGMEM = R"JSON({
  "schema":"fermentlab.presets.v1",
  "revision":1,
  "items":[
    {
      "id":"classica-esempio",
      "name":"Pizza classica - esempio",
      "reading_interval_s":10,
      "total_flour_g":1000,
      "hydration_pct":65,
      "salt_pct":2.8,
      "yeast_type":"fresh",
      "yeast_pct":0.1,
      "autolyse":false,
      "autolyse_min":0,
      "flours":[{"flour_id":"caputo-pizzeria","pct":100}],
      "notes":"Preset dimostrativo: adattare tempi e dosi alle proprie condizioni."
    },
    {
      "id":"contemporanea-esempio",
      "name":"Pizza contemporanea - esempio",
      "reading_interval_s":60,
      "total_flour_g":1000,
      "hydration_pct":72,
      "salt_pct":2.7,
      "yeast_type":"dry",
      "yeast_pct":0.1,
      "autolyse":true,
      "autolyse_min":30,
      "flours":[{"flour_id":"caputo-nuvola","pct":100}],
      "notes":"Preset dimostrativo: adattare tempi e dosi alle proprie condizioni."
    }
  ]
})JSON";

const char DEFAULT_DRAFT[] PROGMEM = R"JSON({
  "schema":"fermentlab.session-draft.v1",
  "revision":1,
  "name":"Nuovo impasto",
  "preset_id":"classica-esempio",
  "reading_interval_s":10,
  "total_flour_g":1000,
  "hydration_pct":65,
  "salt_pct":2.8,
  "yeast_type":"fresh",
  "yeast_pct":0.1,
  "autolyse":false,
  "autolyse_min":0,
  "initial_dough_mass_g":null,
  "flours":[{"flour_id":"caputo-pizzeria","pct":100}],
  "notes":""
})JSON";

bool finiteNumber(JsonVariantConst value, float minimum, float maximum,
                  bool optional = false) {
  if (value.isNull()) {
    return optional;
  }
  if (!value.is<float>() && !value.is<int>() && !value.is<long>()) {
    return false;
  }
  const float number = value.as<float>();
  return std::isfinite(number) && number >= minimum && number <= maximum;
}

bool validId(const char* value) {
  if (value == nullptr || *value == '\0' || strlen(value) > 48) {
    return false;
  }
  for (const char* cursor = value; *cursor; ++cursor) {
    const char c = *cursor;
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-')) {
      return false;
    }
  }
  return true;
}

String normalizeId(const String& value) {
  String output;
  output.reserve(48);
  bool previousWasDash = false;
  const auto appendLetterOrNumber = [&](char character) {
    if (output.length() >= 48) return;
    output += character;
    previousWasDash = false;
  };
  const auto appendSeparator = [&]() {
    if (!previousWasDash && output.length() > 0 && output.length() < 48) {
      output += '-';
      previousWasDash = true;
    }
  };

  for (size_t index = 0; index < value.length(); ++index) {
    const unsigned char raw = static_cast<unsigned char>(value[index]);
    if (raw >= 'A' && raw <= 'Z') {
      appendLetterOrNumber(static_cast<char>(raw - 'A' + 'a'));
    } else if ((raw >= 'a' && raw <= 'z') || (raw >= '0' && raw <= '9')) {
      appendLetterOrNumber(static_cast<char>(raw));
    } else if (raw == 0xC3 && index + 1 < value.length()) {
      // Fold the Latin-1 characters most likely to occur in Italian and
      // European flour/recipe names. Arduino String stores UTF-8 bytes, so
      // handling the two-byte sequence explicitly keeps IDs deterministic.
      const unsigned char continuation =
          static_cast<unsigned char>(value[++index]);
      char folded = '\0';
      if ((continuation >= 0x80 && continuation <= 0x85) ||
          (continuation >= 0xA0 && continuation <= 0xA5)) {
        folded = 'a';
      } else if (continuation == 0x87 || continuation == 0xA7) {
        folded = 'c';
      } else if ((continuation >= 0x88 && continuation <= 0x8B) ||
                 (continuation >= 0xA8 && continuation <= 0xAB)) {
        folded = 'e';
      } else if ((continuation >= 0x8C && continuation <= 0x8F) ||
                 (continuation >= 0xAC && continuation <= 0xAF)) {
        folded = 'i';
      } else if (continuation == 0x91 || continuation == 0xB1) {
        folded = 'n';
      } else if ((continuation >= 0x92 && continuation <= 0x96) ||
                 (continuation >= 0xB2 && continuation <= 0xB6)) {
        folded = 'o';
      } else if ((continuation >= 0x99 && continuation <= 0x9C) ||
                 (continuation >= 0xB9 && continuation <= 0xBC)) {
        folded = 'u';
      } else if (continuation == 0x9D || continuation == 0xBD ||
                 continuation == 0xBF) {
        folded = 'y';
      } else if (continuation == 0x9F) {
        appendLetterOrNumber('s');
        appendLetterOrNumber('s');
      }
      if (folded != '\0') {
        appendLetterOrNumber(folded);
      } else if (continuation != 0x9F) {
        appendSeparator();
      }
    } else {
      appendSeparator();
    }
    if (output.length() >= 48) {
      break;
    }
  }

  while (output.endsWith("-")) {
    output.remove(output.length() - 1);
  }
  return output;
}

String escapedResult(const String& input) {
  String result;
  result.reserve(input.length() + 8);
  for (size_t i = 0; i < input.length(); ++i) {
    const char c = input[i];
    if (c == '"' || c == '\\') result += '\\';
    if (c == '\n' || c == '\r') {
      result += ' ';
    } else {
      result += c;
    }
  }
  return result;
}

}  // namespace

bool SessionConfigStore::begin(fs::FS& filesystem) {
  filesystem_ = &filesystem;
  if (!filesystem.exists(Config::RECIPE_CONFIG_DIRECTORY) &&
      !filesystem.mkdir(Config::RECIPE_CONFIG_DIRECTORY)) {
    return false;
  }
  ready_ = ensureFile(Config::FLOURS_FILE, DEFAULT_FLOURS) &&
           ensureFile(Config::PRESETS_FILE, DEFAULT_PRESETS) &&
           ensureFile(Config::SESSION_DRAFT_FILE, DEFAULT_DRAFT);
  if (!ready_) return false;

  String error;
  ready_ = validateFlours(floursJson(), error) &&
           validatePresets(presetsJson(), error) &&
           validateDraft(draftJson(), error) &&
           validateDraftPresetReference(draftJson(), presetsJson(), error);
  return ready_;
}

String SessionConfigStore::floursJson() const {
  return readFile(Config::FLOURS_FILE, Config::CONFIG_DOCUMENT_MAX_BYTES);
}

String SessionConfigStore::presetsJson() const {
  return readFile(Config::PRESETS_FILE, Config::CONFIG_DOCUMENT_MAX_BYTES);
}

String SessionConfigStore::draftJson() const {
  return readFile(Config::SESSION_DRAFT_FILE, Config::CONFIG_DOCUMENT_MAX_BYTES);
}

String SessionConfigStore::backupJson() const {
  JsonDocument backup;
  backup["schema"] = "fermentlab.backup.v1";
  JsonDocument flours;
  JsonDocument presets;
  JsonDocument draft;
  if (deserializeJson(flours, floursJson()) ||
      deserializeJson(presets, presetsJson()) ||
      deserializeJson(draft, draftJson())) {
    return resultJson(false, "Impossibile leggere la configurazione.");
  }
  backup["flours"] = flours.as<JsonVariantConst>();
  backup["presets"] = presets.as<JsonVariantConst>();
  backup["draft"] = draft.as<JsonVariantConst>();
  String output;
  serializeJsonPretty(backup, output);
  return output;
}

String SessionConfigStore::saveFlours(const String& body) {
  JsonDocument document;
  if (deserializeJson(document, body)) {
    return resultJson(false, "JSON del catalogo non valido.");
  }
  JsonArray items = document["items"].as<JsonArray>();
  if (items.isNull()) {
    return resultJson(false, "Catalogo farine non valido.");
  }
  for (JsonObject flour : items) {
    String id = normalizeId(String(flour["id"] | ""));
    if (id.length() == 0) {
      id = normalizeId(String(flour["brand"] | "") + "-" +
                       String(flour["name"] | ""));
    }
    flour["id"] = id;
  }

  String normalized;
  serializeJson(document, normalized);
  String error;
  if (!validateFlours(normalized, error)) return resultJson(false, error);
  const String presets = presetsJson();
  const String draft = draftJson();
  if (!validatePresets(presets, error, &normalized) ||
      !validateDraft(draft, error, &normalized)) {
    return resultJson(false, String("Catalogo incompatibile: ") + error);
  }
  if (!writeAtomic(Config::FLOURS_FILE, normalized)) {
    return resultJson(false, "Scrittura atomica del catalogo fallita.");
  }
  return resultJson(true, "Catalogo farine salvato.");
}

String SessionConfigStore::savePresets(const String& body) {
  JsonDocument document;
  if (deserializeJson(document, body)) {
    return resultJson(false, "JSON dei preset non valido.");
  }
  JsonArray items = document["items"].as<JsonArray>();
  if (items.isNull()) {
    return resultJson(false, "Raccolta preset non valida.");
  }
  for (JsonObject preset : items) {
    String id = normalizeId(String(preset["id"] | ""));
    if (id.length() == 0) {
      id = normalizeId(String(preset["name"] | ""));
    }
    preset["id"] = id;
    yield();
  }

  String normalized;
  serializeJson(document, normalized);
  String error;
  if (!validatePresets(normalized, error)) return resultJson(false, error);
  if (!validateDraftPresetReference(draftJson(), normalized, error)) {
    return resultJson(false, error);
  }
  if (!writeAtomic(Config::PRESETS_FILE, normalized)) {
    return resultJson(false, "Scrittura atomica dei preset fallita.");
  }
  return resultJson(true, "Preset salvati.");
}

String SessionConfigStore::saveDraft(const String& body) {
  JsonDocument document;
  if (deserializeJson(document, body)) {
    return resultJson(false, "JSON dell'impasto non valido.");
  }
  if (!document["preset_id"].isNull()) {
    document["preset_id"] =
        normalizeId(String(document["preset_id"] | ""));
  }
  JsonArray flours = document["flours"].as<JsonArray>();
  if (!flours.isNull()) {
    for (JsonObject component : flours) {
      component["flour_id"] =
          normalizeId(String(component["flour_id"] | ""));
      yield();
    }
  }

  String normalized;
  serializeJson(document, normalized);
  String error;
  if (!validateDraft(normalized, error)) return resultJson(false, error);
  if (!validateDraftPresetReference(normalized, presetsJson(), error)) {
    return resultJson(false, error);
  }
  if (!writeAtomic(Config::SESSION_DRAFT_FILE, normalized)) {
    return resultJson(false, "Scrittura atomica dell'impasto fallita.");
  }
  return resultJson(true, "Prossimo impasto salvato.");
}

String SessionConfigStore::importBackup(const String& body) {
  if (body.length() == 0 || body.length() > Config::CONFIG_BACKUP_MAX_BYTES) {
    return resultJson(false, "Backup vuoto o troppo grande.");
  }
  JsonDocument backup;
  if (deserializeJson(backup, body) ||
      String(backup["schema"] | "") != "fermentlab.backup.v1") {
    return resultJson(false, "Formato backup non riconosciuto.");
  }
  String flours;
  String presets;
  String draft;
  serializeJson(backup["flours"], flours);
  serializeJson(backup["presets"], presets);
  serializeJson(backup["draft"], draft);
  String error;
  if (!validateFlours(flours, error) ||
      !validatePresets(presets, error, &flours) ||
      !validateDraft(draft, error, &flours) ||
      !validateDraftPresetReference(draft, presets, error)) {
    return resultJson(false, String("Backup non valido: ") + error);
  }
  // Each document is individually recoverable. Validate everything before the
  // first write so malformed imports never replace a valid configuration.
  if (!writeAtomic(Config::FLOURS_FILE, flours) ||
      !writeAtomic(Config::PRESETS_FILE, presets) ||
      !writeAtomic(Config::SESSION_DRAFT_FILE, draft)) {
    return resultJson(false, "Importazione interrotta durante il salvataggio.");
  }
  return resultJson(true, "Backup importato.");
}

bool SessionConfigStore::draftValid(String* reason) const {
  String error;
  const bool valid = ready_ && validateDraft(draftJson(), error);
  if (reason != nullptr) {
    *reason = valid ? String() : (error.length() ? error : "Configurazione non disponibile.");
  }
  return valid;
}

String SessionConfigStore::draftName() const {
  JsonDocument document;
  if (deserializeJson(document, draftJson())) return String();
  return String(document["name"] | "");
}

String SessionConfigStore::draftFlourSummary() const {
  JsonDocument draft;
  JsonDocument catalog;
  if (deserializeJson(draft, draftJson()) ||
      deserializeJson(catalog, floursJson())) return String();
  String summary;
  for (JsonObjectConst component : draft["flours"].as<JsonArrayConst>()) {
    const String id = component["flour_id"] | "";
    String label = id;
    for (JsonObjectConst flour : catalog["items"].as<JsonArrayConst>()) {
      if (String(flour["id"] | "") == id) {
        label = String(flour["brand"] | "") + " " + String(flour["name"] | "");
        break;
      }
    }
    if (summary.length()) summary += ", ";
    summary += label;
    summary += " ";
    summary += String(component["pct"].as<float>(), 1);
    summary += "%";
  }
  return summary;
}

float SessionConfigStore::draftHydrationPercent() const {
  JsonDocument document;
  if (deserializeJson(document, draftJson())) return NAN;
  return document["hydration_pct"] | NAN;
}

uint32_t SessionConfigStore::draftReadingIntervalSeconds() const {
  JsonDocument document;
  if (deserializeJson(document, draftJson())) {
    return Config::DEFAULT_READING_INTERVAL_S;
  }
  return document["reading_interval_s"] |
         Config::DEFAULT_READING_INTERVAL_S;
}

bool SessionConfigStore::writeRecipeSnapshot(Print& output) const {
  JsonDocument draft;
  JsonDocument catalog;
  if (deserializeJson(draft, draftJson()) ||
      deserializeJson(catalog, floursJson())) return false;

  JsonDocument snapshot;
  snapshot["name"] = draft["name"];
  snapshot["preset_id"] = draft["preset_id"];
  snapshot["total_flour_g"] = draft["total_flour_g"];
  snapshot["hydration_pct"] = draft["hydration_pct"];
  snapshot["salt_pct"] = draft["salt_pct"];
  snapshot["yeast_type"] = draft["yeast_type"];
  snapshot["yeast_pct"] = draft["yeast_pct"];
  snapshot["autolyse"] = draft["autolyse"];
  snapshot["autolyse_min"] = draft["autolyse_min"];
  snapshot["initial_dough_mass_g"] = draft["initial_dough_mass_g"];
  snapshot["notes"] = draft["notes"];
  const float total = draft["total_flour_g"] | 0.0f;
  JsonArray resolved = snapshot["flours"].to<JsonArray>();
  for (JsonObjectConst component : draft["flours"].as<JsonArrayConst>()) {
    JsonObject item = resolved.add<JsonObject>();
    const String id = component["flour_id"] | "";
    const float pct = component["pct"] | 0.0f;
    item["flour_id"] = id;
    item["pct"] = pct;
    item["grams"] = total * pct / 100.0f;
    for (JsonObjectConst flour : catalog["items"].as<JsonArrayConst>()) {
      if (String(flour["id"] | "") == id) {
        item["catalog_snapshot"] = flour;
        break;
      }
    }
  }
  return serializeJson(snapshot, output) > 0;
}

bool SessionConfigStore::ensureFile(const char* path, const char* defaultJson) {
  if (!recoverAtomicFile(path)) return false;
  if (fileExistsQuiet(path)) return true;
  return writeAtomic(path, String(defaultJson));
}

bool SessionConfigStore::recoverAtomicFile(const char* path) {
  const String backup = String(path) + ".bak";
  const String temporary = String(path) + ".tmp";
  if (!fileExistsQuiet(path) && fileExistsQuiet(backup) &&
      !filesystem_->rename(backup, path)) {
    return false;
  }
  if (fileExistsQuiet(temporary)) filesystem_->remove(temporary);
  if (fileExistsQuiet(path) && fileExistsQuiet(backup)) {
    filesystem_->remove(backup);
  }
  return true;
}

bool SessionConfigStore::writeAtomic(const char* path, const String& content) {
  if (filesystem_ == nullptr || content.length() == 0 ||
      content.length() > Config::CONFIG_DOCUMENT_MAX_BYTES) return false;
  const String temporary = String(path) + ".tmp";
  const String backup = String(path) + ".bak";
  if (fileExistsQuiet(temporary)) filesystem_->remove(temporary);
  File file = filesystem_->open(temporary, FILE_WRITE);
  if (!file) return false;
  const size_t written = file.print(content);
  file.flush();
  file.close();
  if (written != content.length()) {
    filesystem_->remove(temporary);
    return false;
  }
  if (fileExistsQuiet(backup)) filesystem_->remove(backup);
  const bool hadOriginal = fileExistsQuiet(path);
  if (hadOriginal && !filesystem_->rename(path, backup)) {
    filesystem_->remove(temporary);
    return false;
  }
  if (!filesystem_->rename(temporary, path)) {
    if (hadOriginal) filesystem_->rename(backup, path);
    return false;
  }
  if (hadOriginal) filesystem_->remove(backup);
  return true;
}

bool SessionConfigStore::fileExistsQuiet(const String& path) const {
  if (filesystem_ == nullptr || path.length() < 2) return false;
  const int separator = path.lastIndexOf('/');
  const String directoryPath = separator <= 0 ? String("/")
                                               : path.substring(0, separator);
  const String targetName = path.substring(separator + 1);
  File directory = filesystem_->open(directoryPath, FILE_READ);
  if (!directory || !directory.isDirectory()) {
    if (directory) directory.close();
    return false;
  }
  bool found = false;
  for (File entry = directory.openNextFile(); entry;
       entry = directory.openNextFile()) {
    String entryName = entry.name();
    const int entrySeparator = entryName.lastIndexOf('/');
    if (entrySeparator >= 0) entryName = entryName.substring(entrySeparator + 1);
    found = entryName == targetName;
    entry.close();
    if (found) break;
  }
  directory.close();
  return found;
}

String SessionConfigStore::readFile(const char* path,
                                    size_t maximumBytes) const {
  if (filesystem_ == nullptr) return String();
  File file = filesystem_->open(path, FILE_READ);
  if (!file || file.size() > maximumBytes) {
    if (file) file.close();
    return String();
  }
  String output;
  output.reserve(file.size() + 1);
  while (file.available()) output += static_cast<char>(file.read());
  file.close();
  return output;
}

bool SessionConfigStore::validateFlours(const String& content,
                                        String& error) const {
  if (content.length() == 0 || content.length() > Config::CONFIG_DOCUMENT_MAX_BYTES) {
    error = "Catalogo vuoto o troppo grande.";
    return false;
  }
  JsonDocument document;
  if (deserializeJson(document, content)) {
    error = "JSON del catalogo non valido.";
    return false;
  }
  JsonArrayConst items = document["items"].as<JsonArrayConst>();
  if (items.isNull() || items.size() == 0 || items.size() > 30) {
    error = "Il catalogo deve contenere da 1 a 30 farine.";
    return false;
  }
  for (size_t index = 0; index < items.size(); ++index) {
    JsonObjectConst item = items[index];
    const char* id = item["id"] | "";
    const char* brand = item["brand"] | "";
    const char* name = item["name"] | "";
    if (!validId(id) || *brand == '\0' || *name == '\0') {
      error = "Ogni farina richiede id, marca e nome validi.";
      return false;
    }
    for (size_t other = index + 1; other < items.size(); ++other) {
      if (String(items[other]["id"] | "") == id) {
        error = String("ID farina duplicato: ") + id;
        return false;
      }
    }
    if (!finiteNumber(item["protein_pct"], 0, 30, true) ||
        !finiteNumber(item["w_min"], 50, 700, true) ||
        !finiteNumber(item["w_max"], 50, 700, true) ||
        !finiteNumber(item["pl_min"], 0, 5, true) ||
        !finiteNumber(item["pl_max"], 0, 5, true)) {
      error = String("Valori tecnici non validi per ") + id + ".";
      return false;
    }
  }
  return true;
}

bool SessionConfigStore::validatePresets(const String& content,
                                         String& error,
                                         const String* catalogOverride) const {
  if (content.length() == 0 || content.length() > Config::CONFIG_DOCUMENT_MAX_BYTES) {
    error = "Preset vuoti o troppo grandi.";
    return false;
  }
  JsonDocument document;
  if (deserializeJson(document, content)) {
    error = "JSON dei preset non valido.";
    return false;
  }
  JsonArrayConst items = document["items"].as<JsonArrayConst>();
  if (items.isNull() || items.size() > 20) {
    error = "La raccolta preset non è valida (massimo 20).";
    return false;
  }
  for (size_t index = 0; index < items.size(); ++index) {
    yield();
    JsonObjectConst item = items[index];
    if (!validId(item["id"] | "") || String(item["name"] | "").isEmpty()) {
      error = "Ogni preset richiede id e nome.";
      return false;
    }
    for (size_t other = index + 1; other < items.size(); ++other) {
      if (String(items[other]["id"] | "") == String(item["id"] | "")) {
        error = String("ID preset duplicato: ") + String(item["id"] | "");
        return false;
      }
    }
    String serialized;
    JsonDocument draft;
    draft["name"] = item["name"];
    draft["preset_id"] = item["id"];
    draft["reading_interval_s"] =
        item["reading_interval_s"] | Config::DEFAULT_READING_INTERVAL_S;
    draft["total_flour_g"] = item["total_flour_g"];
    draft["hydration_pct"] = item["hydration_pct"];
    draft["salt_pct"] = item["salt_pct"];
    draft["yeast_type"] = item["yeast_type"];
    draft["yeast_pct"] = item["yeast_pct"];
    draft["autolyse"] = item["autolyse"];
    draft["autolyse_min"] = item["autolyse_min"];
    draft["initial_dough_mass_g"] = nullptr;
    draft["flours"] = item["flours"];
    draft["notes"] = item["notes"];
    serializeJson(draft, serialized);
    if (!validateDraft(serialized, error, catalogOverride)) {
      error = String("Preset ") + String(item["id"] | "") + ": " + error;
      return false;
    }
  }
  return true;
}

bool SessionConfigStore::validateDraft(const String& content,
                                       String& error,
                                       const String* catalogOverride) const {
  if (content.length() == 0 || content.length() > Config::CONFIG_DOCUMENT_MAX_BYTES) {
    error = "Impasto vuoto o troppo grande.";
    return false;
  }
  JsonDocument document;
  if (deserializeJson(document, content)) {
    error = "JSON dell'impasto non valido.";
    return false;
  }
  if (String(document["name"] | "").isEmpty() ||
      (!document["reading_interval_s"].isNull() &&
       !finiteNumber(document["reading_interval_s"],
                     Config::MIN_READING_INTERVAL_S,
                     Config::MAX_READING_INTERVAL_S)) ||
      !finiteNumber(document["total_flour_g"], 1, 100000) ||
      !finiteNumber(document["hydration_pct"], 0, 200) ||
      !finiteNumber(document["salt_pct"], 0, 20) ||
      !finiteNumber(document["yeast_pct"], 0, 20) ||
      !finiteNumber(document["autolyse_min"], 0, 10080) ||
      !finiteNumber(document["initial_dough_mass_g"], 1, 200000, true)) {
    error = "Nome o quantità dell'impasto non validi.";
    return false;
  }
  const String yeastType = document["yeast_type"] | "";
  if (yeastType != "fresh" && yeastType != "dry" && yeastType != "sourdough" &&
      yeastType != "none") {
    error = "Tipo di lievito non riconosciuto.";
    return false;
  }

  JsonDocument catalog;
  const String catalogContent =
      catalogOverride == nullptr ? floursJson() : *catalogOverride;
  if (deserializeJson(catalog, catalogContent)) {
    error = "Catalogo farine non disponibile o non valido.";
    return false;
  }
  const JsonArrayConst catalogItems = catalog["items"].as<JsonArrayConst>();
  if (catalogItems.isNull() || catalogItems.size() == 0) {
    error = "Catalogo farine vuoto o non valido.";
    return false;
  }

  const auto flourIdExists = [&](const String& flourId) {
    for (JsonObjectConst item : catalogItems) {
      if (String(item["id"] | "") == flourId) {
        return true;
      }
    }
    return false;
  };

  JsonArrayConst flours = document["flours"].as<JsonArrayConst>();
  if (flours.isNull() || flours.size() == 0 || flours.size() > 8) {
    error = "Servono da 1 a 8 farine nell'impasto.";
    return false;
  }
  float totalPct = 0;
  for (JsonObjectConst component : flours) {
    yield();
    const String id = component["flour_id"] | "";
    if (id.isEmpty() || !flourIdExists(id) ||
        !finiteNumber(component["pct"], 0.01f, 100.0f)) {
      error = String("Farina o percentuale non valida: ") + id;
      return false;
    }
    totalPct += component["pct"].as<float>();
  }
  if (fabsf(totalPct - 100.0f) > 0.15f) {
    error = "Le percentuali delle farine devono sommare 100%.";
    return false;
  }
  return true;
}

bool SessionConfigStore::validateDraftPresetReference(
    const String& draftContent, const String& presetsContent,
    String& error) const {
  JsonDocument draft;
  JsonDocument presets;
  if (deserializeJson(draft, draftContent) ||
      deserializeJson(presets, presetsContent)) {
    error = "Impossibile verificare il preset della bozza.";
    return false;
  }
  if (draft["preset_id"].isNull()) return true;
  const String presetId = draft["preset_id"] | "";
  if (presetId.isEmpty()) {
    error = "preset_id deve essere nullo oppure un ID valido.";
    return false;
  }
  for (JsonObjectConst preset : presets["items"].as<JsonArrayConst>()) {
    if (String(preset["id"] | "") == presetId) return true;
  }
  error = String("La bozza usa il preset inesistente: ") + presetId +
          ". Applicare un altro preset prima di rinominarlo o eliminarlo.";
  return false;
}

String SessionConfigStore::resultJson(bool ok, const String& message) const {
  return String("{\"ok\":") + (ok ? "true" : "false") +
         ",\"message\":\"" + escapedResult(message) + "\"}";
}
