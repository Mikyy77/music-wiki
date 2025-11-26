#!/usr/bin/env python3
"""Test script to verify false positive filtering works correctly."""

from wiki_music_extractor import WikiMusicExtractor

def test_false_positives():
    extractor = WikiMusicExtractor()
    
    test_cases = [
        # (title, text_snippet, categories, expected_result, description)
        (
            "Bandwidth (signal processing)",
            "{{Infobox thing\n}}",
            ["Signal processing", "Telecommunication theory"],
            None,
            "Should REJECT - telecommunications bandwidth"
        ),
        (
            "Wireless broadband",
            "{{Infobox thing\n}}",
            ["Wireless networking", "Broadband"],
            None,
            "Should REJECT - internet technology"
        ),
        (
            "The Beatles",
            "{{Infobox musical artist\n}}",
            ["English rock bands", "Musical groups"],
            "band",
            "Should ACCEPT - legitimate band"
        ),
        (
            "Abandonment of an action",
            "Some legal text",
            ["Legal terminology"],
            None,
            "Should REJECT - legal term with 'band' substring"
        ),
        (
            "Rock band",
            "{{Infobox band\n}}",
            ["Rock bands", "Musical groups"],
            "band",
            "Should ACCEPT - generic band with music categories"
        ),
        (
            "Frequency band",
            "Some text about frequency bands",
            ["Radio spectrum", "Telecommunications"],
            None,
            "Should REJECT - radio frequency bands"
        ),
        (
            "Jazz Band Name",
            "A jazz group",
            ["Jazz bands", "American jazz ensembles"],
            "band",
            "Should ACCEPT - has 'band' word and music categories"
        ),
        (
            "Something with band",
            "No infobox",
            ["General topics"],
            None,
            "Should REJECT - has 'band' but no music categories"
        ),
        (
            "Bob Dylan",
            "{{Infobox musical artist\n}}",
            ["American singer-songwriters", "Folk musicians"],
            "artist",
            "Should ACCEPT - legitimate artist"
        ),
    ]
    
    print("Testing False Positive Filtering\n" + "="*80)
    
    passed = 0
    failed = 0
    
    for title, text, categories, expected, description in test_cases:
        result = extractor.is_music_related(title, text, categories)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status}: {description}")
        print(f"  Title: {title}")
        print(f"  Expected: {expected}, Got: {result}")
    
    print("\n" + "="*80)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"False positives filtered during test: {extractor.stats['filtered_false_positives']}")
    
    return failed == 0

if __name__ == "__main__":
    success = test_false_positives()
    exit(0 if success else 1)
