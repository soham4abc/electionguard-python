from typing import cast, TypeVar, Callable, List, Tuple
import os
from random import Random, randint
import uuid

from jsons import KEY_TRANSFORMER_SNAKECASE, loads

from hypothesis.strategies import (
    composite,
    booleans,
    integers,
    text,
    uuids,
    SearchStrategy,
)

from electionguard.ballot import (
    PlaintextBallot,
    PlaintextBallotContest,
    PlaintextBallotSelection,
)
from electionguard.encrypt import selection_from
from electionguard.manifest import (
    ContestDescription,
    SelectionDescription,
    InternalManifest,
)


_T = TypeVar("_T")
_DrawType = Callable[[SearchStrategy[_T]], _T]

data = os.path.realpath(os.path.join(__file__, "../../../data"))


class BallotFactory:
    """Factory to create ballots"""

    simple_ballot_filename = "ballot_in_simple.json"
    simple_ballots_filename = "plaintext_ballots_simple.json"

    @staticmethod
    def get_random_selection_from(
        description: SelectionDescription,
        random_source: Random,
        is_placeholder=False,
    ) -> PlaintextBallotSelection:

        selected = bool(random_source.randint(0, 1))
        return selection_from(description, is_placeholder, selected)

    def get_random_contest_from(
        self,
        description: ContestDescription,
        random: Random,
        suppress_validity_check=False,
        with_trues=False,
    ) -> PlaintextBallotContest:
        """
        Get a randomly filled contest for the given description that
        may be undervoted and may include explicitly false votes.
        Since this is only used for testing, the random number generator
        (`random`) must be provided to make this function deterministic.
        """
        if not suppress_validity_check:
            assert description.is_valid(), "the contest description must be valid"

        selections: List[PlaintextBallotSelection] = list()

        voted = 0

        for selection_description in description.ballot_selections:
            selection = self.get_random_selection_from(selection_description, random)
            # the caller may force a true value
            voted += selection.vote
            if voted <= 1 and selection.vote and with_trues:
                selections.append(selection)
                continue

            # Possibly append the true selection, indicating an undervote
            if voted <= description.number_elected and bool(random.randint(0, 1)) == 1:
                selections.append(selection)
            # Possibly append the false selections as well, indicating some choices
            # may be explicitly false
            elif bool(random.randint(0, 1)) == 1:
                selections.append(selection_from(selection_description))

        return PlaintextBallotContest(description.object_id, selections)

    def get_fake_ballot(
        self,
        internal_manifest: InternalManifest,
        ballot_id: str = None,
        with_trues=True,
    ) -> PlaintextBallot:
        """
        Get a single Fake Ballot object that is manually constructed with default vaules
        """

        if ballot_id is None:
            ballot_id = "some-unique-ballot-id-123"

        contests: List[PlaintextBallotContest] = []
        for contest in internal_manifest.get_contests_for(
            internal_manifest.ballot_styles[0].object_id
        ):
            contests.append(
                self.get_random_contest_from(contest, Random(), with_trues=with_trues)
            )

        fake_ballot = PlaintextBallot(
            ballot_id, internal_manifest.ballot_styles[0].object_id, contests
        )

        return fake_ballot

    def generate_fake_plaintext_ballots_for_election(
        self, internal_manifest: InternalManifest, number_of_ballots: int
    ) -> List[PlaintextBallot]:
        ballots: List[PlaintextBallot] = []
        for _i in range(number_of_ballots):

            style_index = randint(0, len(internal_manifest.ballot_styles) - 1)
            ballot_style = internal_manifest.ballot_styles[style_index]
            ballot_id = f"ballot-{uuid.uuid1()}"

            contests: List[PlaintextBallotContest] = []
            for contest in internal_manifest.get_contests_for(ballot_style.object_id):
                contests.append(
                    self.get_random_contest_from(contest, Random(), with_trues=True)
                )

            ballots.append(PlaintextBallot(ballot_id, ballot_style.object_id, contests))

        return ballots

    def get_simple_ballot_from_file(self) -> PlaintextBallot:
        return self._get_ballot_from_file(self.simple_ballot_filename)

    def get_simple_ballots_from_file(self) -> List[PlaintextBallot]:
        return self._get_ballots_from_file(self.simple_ballots_filename)

    @staticmethod
    def _get_ballot_from_file(filename: str) -> PlaintextBallot:
        with open(os.path.join(data, filename), "r") as subject:
            result = subject.read()
            target = PlaintextBallot.from_json(result)
        return target

    @staticmethod
    def _get_ballots_from_file(filename: str) -> List[PlaintextBallot]:
        with open(os.path.join(data, filename), "r") as subject:
            result = subject.read()
            target = cast(
                List[PlaintextBallot],
                loads(
                    result,
                    List[PlaintextBallot],
                    key_transformer=KEY_TRANSFORMER_SNAKECASE,
                ),
            )
        return target


@composite
def get_selection_well_formed(
    draw: _DrawType, ids=uuids(), bools=booleans(), txt=text(), vote=integers(0, 1)
) -> Tuple[str, PlaintextBallotSelection]:
    use_none = draw(bools)
    if use_none:
        extra_data = None
    else:
        extra_data = draw(txt)
    object_id = f"selection-{draw(ids)}"
    return (
        object_id,
        PlaintextBallotSelection(object_id, draw(vote), draw(bools), extra_data),
    )


@composite
def get_selection_poorly_formed(
    draw: _DrawType, ids=uuids(), bools=booleans(), txt=text(), vote=integers(0, 1)
) -> Tuple[str, PlaintextBallotSelection]:
    use_none = draw(bools)
    if use_none:
        extra_data = None
    else:
        extra_data = draw(txt)
    object_id = f"selection-{draw(ids)}"
    return (
        object_id,
        PlaintextBallotSelection(object_id, draw(vote), draw(bools), extra_data),
    )
