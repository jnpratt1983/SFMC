"""Pull field metadata for the dictionary objects from Salesforce."""
import glob, os, re
from common import save, log
from sf_client import SF, API

OBJECTS = ["Lead", "Contact", "Account", "Bill__c", "Monthly_Driving_Stat__c"]


def main():
    sf = SF()
    desc = {o: sf.describe(o) for o in OBJECTS}
    save("sf_describe", desc)

    ents = sf.query("SELECT DurableId, QualifiedApiName, Label, PluralLabel FROM EntityDefinition WHERE QualifiedApiName IN ('%s')" % "','".join(OBJECTS))
    save("sf_entities", ents)
    rows = []
    for e in ents:
        rows += sf.query(
            "SELECT Id, DeveloperName, TableEnumOrId, CreatedDate, CreatedBy.Name, LastModifiedDate, LastModifiedBy.Name, "
            "Description, InlineHelpText, NamespacePrefix FROM CustomField WHERE TableEnumOrId='%s'" % e["DurableId"], tooling=True)
    save("sf_customfields", rows)
    fd = []
    for o in OBJECTS:
        fd += sf.query(
            "SELECT QualifiedApiName, EntityDefinition.QualifiedApiName, Label, DataType, Description, BusinessOwnerId, BusinessOwner.Name, "
            "BusinessStatus, SecurityClassification, ComplianceGroup, IsIndexed, IsCalculated, IsFieldHistoryTracked, LastModifiedDate, "
            "LastModifiedBy.Name FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName='%s'" % o)
    save("sf_fielddefs", fd)

    # Data Cloud package-kit field maps (standard field -> DMO field) live only in the Metadata API.
    names = sf.list_metadata("DataSrcDataModelFieldMap")
    maps = []
    if names:
        folder = sf.retrieve_metadata({"DataSrcDataModelFieldMap": names})
        for f in glob.glob(os.path.join(folder, "dataSrcDataModelFieldMaps", "*")):
            x = open(f).read()
            s = re.search(r"<sourceField>([^<]+)</sourceField>", x)
            t = re.search(r"<targetField>([^<]+)</targetField>", x)
            if s and t:
                maps.append({"source": s.group(1), "target": t.group(1)})
    save("dc_kit_fieldmaps", maps)
    log("kit field maps", len(maps))

    # Flows and Apex that read Data Cloud objects (used for CI "where used" in Salesforce)
    folder = sf.retrieve_metadata({"Flow": ["*"], "ApexClass": ["*"]})
    refs = []
    for f in glob.glob(os.path.join(folder, "flows", "*")) + glob.glob(os.path.join(folder, "classes", "*.cls")):
        x = open(f, errors="replace").read()
        hits = sorted(set(re.findall(r"\b([A-Za-z0-9_]+__(?:cio|dlm))\b", x)))
        if hits:
            refs.append({"type": "Flow" if "/flows/" in f else "ApexClass", "name": os.path.basename(f).split(".")[0], "objects": hits})
    save("sf_dc_refs", refs)
    log("flows/apex referencing Data Cloud objects", len(refs))


if __name__ == "__main__":
    main()
